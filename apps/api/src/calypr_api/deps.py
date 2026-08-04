"""Per-request tenant resolution.

The public API can't trust a raw user-id header from the internet, so when `CALYPR_INTERNAL_KEY`
is set the Next proxy must present it (`X-Calypr-Internal-Key`) alongside `X-Calypr-User-Id`; the
API then maps that user to a workspace via the `resolve_workspace()` SQL function and scopes the
session to it (the RLS GUC). With no key set (local / CI / E2E), every request falls back to the
shared dev workspace — so existing tests keep working unchanged.

Since 0016 a user can own several workspaces, so the browser also *claims* one via
`X-Calypr-Workspace-Id` (forwarded by the Next proxy from a cookie). **That claim is never
trusted.** It goes to SQL as an argument, and `resolve_workspace(user, workspace)` returns it only
if it belongs to the caller's account — otherwise the caller gets their own default workspace.
The proxy is trusted to assert *who you are*; nothing is trusted to assert *what you may open*.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from calypr_api import entitlements
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.session import SessionLocal, get_session, set_tenant

log = logging.getLogger(__name__)

#: The workspace the browser is asking for. A *claim*, validated in SQL against the caller's
#: account — see the module docstring.
WORKSPACE_HEADER = "x-calypr-workspace-id"

#: Raised by `resolve_account` when the account has been soft-deleted (migration 0017).
_DELETED_ACCOUNT_SQLSTATE = "CY001"


def is_account_deleted(exc: BaseException) -> bool:
    """Whether this exception is `resolve_account` refusing a soft-deleted account.

    Matched on **SQLSTATE**, never on the message. The message is a human string that carries a
    user id and is free to be reworded, translated by a driver, or wrapped; the code is part of
    the function's contract with this module. Matching text here would turn a copy-edit in a
    migration into a silent authentication bypass."""
    orig = getattr(exc, "orig", None)
    return getattr(orig, "sqlstate", None) == _DELETED_ACCOUNT_SQLSTATE

#: A workspace's plan now lives on its account. Every gate that used to read `workspace.plan`
#: reads through this join instead.
_PLAN_FOR_WORKSPACE = (
    "SELECT a.plan FROM billing_account a JOIN workspace w ON w.account_id = a.id WHERE w.id = :id"
)


def _claimed_workspace(request: Request) -> uuid.UUID | None:
    """The workspace id the caller is asking for, if it's even well-formed.

    A missing or malformed claim is simply no claim — never a 4xx. The value comes from a cookie
    that can go stale in perfectly ordinary ways (the workspace was deleted, someone else signed
    in on this machine), and erroring would wedge the dashboard with no way back. SQL decides
    whether a well-formed claim is *allowed*; this only decides whether it's parseable."""
    raw = request.headers.get(WORKSPACE_HEADER)
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        log.info("ignoring malformed workspace claim")
        return None


@dataclass
class Tenant:
    """The resolved workspace for a request, plus the session scoped to it."""

    session: Session
    workspace_id: uuid.UUID
    # The signed-in user's verified email, asserted by the trusted proxy (None in dev/CI, where
    # every request falls back to the shared dev workspace). Used to match against the beta
    # invite list — see `entitlements.grant_beta_if_invited`.
    email: str | None = None


def _resolve_workspace_id(request: Request, session: Session) -> uuid.UUID:
    """The workspace a request belongs to. Dev/CI (no internal key) → the shared dev
    workspace, resolved without touching the DB. With an internal key set, the trusted Next
    proxy must present it plus the user id, which — together with the caller's workspace claim —
    is mapped to a workspace via SQL."""
    if not settings.internal_key:
        return uuid.UUID(DEV_WORKSPACE_ID)
    if request.headers.get("x-calypr-internal-key") != settings.internal_key:
        raise HTTPException(status_code=401, detail="unauthorized")
    user_id = request.headers.get("x-calypr-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="missing user")
    claimed = _claimed_workspace(request)
    try:
        resolved = session.execute(
            text("SELECT resolve_workspace(:uid, :ws)"), {"uid": user_id, "ws": claimed}
        ).scalar_one()
    except DBAPIError as exc:
        if not is_account_deleted(exc):
            raise
        # The RAISE aborted the transaction, so this session can't run another statement until
        # it's rolled back. Without this the 401 is followed by an InFailedSqlTransaction on the
        # way out (FastAPI's dependency teardown commits or closes), turning a clean 401 into a
        # 500 — the failure mode that makes a deleted account look like a broken server.
        session.rollback()
        # 401, not 403: the account genuinely no longer exists, so this is "we don't know who
        # you are" rather than "you may not". It also matches what these routes already return
        # for a bad internal key or a missing user, so the web layer needs no new branch.
        raise HTTPException(status_code=401, detail="account deleted") from exc
    # Commit the find-or-create immediately. It is a side effect that has to outlive the request,
    # and most requests are reads that never commit — so without this a brand-new user's account
    # and workspace were rolled back on the way out and rebuilt, with fresh ids, on every single
    # request until the first *writing* one happened to persist them. The unique constraint on
    # `owner_user_id` hid it (the row settled as soon as anything committed) but the churn was
    # real, and with a workspace switcher it becomes visible: the id in the cookie would never
    # match anything. Safe to commit here because nothing else has touched this session yet.
    session.commit()
    resolved_id = uuid.UUID(str(resolved))
    if claimed is not None and claimed != resolved_id:
        # Not an error — a stale or foreign claim falls back by design — but worth seeing, since
        # it's also what a cross-tenant probe looks like.
        log.info("rejected workspace claim %s; served %s", claimed, resolved_id)
    return resolved_id


def tenant(request: Request, session: Session = Depends(get_session)) -> Tenant:
    ws = _resolve_workspace_id(request, session)
    set_tenant(session, str(ws))
    return Tenant(
        session=session,
        workspace_id=ws,
        email=request.headers.get("x-calypr-user-email"),
    )


def request_workspace(request: Request) -> uuid.UUID:
    """Workspace id for a compute route (`/runs`, `/assist`) WITHOUT requiring a DB session in
    dev/CI.

    Unlike the data routes, the streaming routes don't hold `tenant`'s session for the whole
    request — they only need the workspace id up front (to scope the assist daily cap, and to
    tag best-effort metering rows the `RunRecorder` writes on its *own* session). In dev/CI
    that's the shared dev workspace, resolved with no DB, so both routes work in DB-less local
    dev (matching start.sh's promise). With an internal key set, the trusted proxy must present
    it plus the user id, mapped to a workspace via SQL."""
    if not settings.internal_key:
        return uuid.UUID(DEV_WORKSPACE_ID)
    with SessionLocal() as session:
        return _resolve_workspace_id(request, session)


# It's no longer assist-specific (metering now uses it too); keep the old name as an alias.
assist_workspace = request_workspace


def run_workspace(request: Request) -> uuid.UUID:
    """Workspace id for `/runs` — the public playground. Unlike `request_workspace` this NEVER
    401s: the playground is anonymous by design (the web `/api/runs` proxy is intentionally not
    tenant-scoped). An authenticated proxy call (internal key + user id) resolves to that user's
    workspace so metering attributes correctly; anonymous calls, a missing/invalid key, a
    missing user, or any DB error all fall back to the shared dev workspace so runs always
    stream (start.sh's DB-less promise)."""
    dev = uuid.UUID(DEV_WORKSPACE_ID)
    if not settings.internal_key:
        return dev
    if request.headers.get("x-calypr-internal-key") != settings.internal_key:
        return dev
    user_id = request.headers.get("x-calypr-user-id")
    if not user_id:
        return dev
    try:
        with SessionLocal() as session:
            resolved = session.execute(
                text("SELECT resolve_workspace(:uid, :ws)"),
                {"uid": user_id, "ws": _claimed_workspace(request)},
            ).scalar_one()
            # Commit for the same reason `_resolve_workspace_id` does — and this path is where
            # skipping it actually cost something. `/runs` never writes through this session, so
            # the find-or-create was rolled back on the way out and the id handed back named a
            # workspace that did not exist. `RunRecorder.start` then failed its foreign key,
            # logged "run metering disabled", and the run streamed **unmetered and undebited**.
            # A new user's first runs were free, silently.
            session.commit()
        return uuid.UUID(str(resolved))
    except DBAPIError as exc:
        # **Checked before the blanket fallback below, and it must stay that way.** Falling back
        # to the shared dev workspace here would let a deleted account keep streaming runs —
        # metered against, and debited from, the dev account. "Always stream" is the right
        # default for an anonymous visitor or a DB hiccup; it is exactly the wrong one for a
        # caller we have positively identified as deleted.
        if is_account_deleted(exc):
            raise HTTPException(status_code=401, detail="account deleted") from exc
        return dev
    except Exception:
        return dev


def require_code_export(request: Request) -> None:
    """402 unless the caller's workspace may export code (`/parse` — "Apply to canvas").

    Code export is a paid entitlement (`entitlements.has_roundtrip`). The web gate in
    `flags.ts` hides the UI, but hiding a button is not a paywall — this is the enforcement,
    because `/parse` is reachable directly.

    **Enforced only on real deployments** (`CALYPR_INTERNAL_KEY` set). Without one, every
    request falls back to the shared dev workspace (see `_resolve_workspace_id`), which is
    `free` — gating there would make it impossible for local dev, CI, or the e2e suite to
    exercise the very path they cover. Same dev/CI carve-out the connector SSRF guard uses.

    Fails **closed** on a deployment: an unresolvable workspace or a missing row is not
    entitled, rather than falling back to the dev workspace the way metering does. Metering
    guesses so a run always streams; this decides who is paying."""
    if not settings.internal_key:
        return
    with SessionLocal() as session:
        workspace_id = _resolve_workspace_id(request, session)  # 401s on a bad key / no user
        plan = session.execute(
            text(_PLAN_FOR_WORKSPACE), {"id": str(workspace_id)}
        ).scalar_one_or_none()
    if not entitlements.has_roundtrip(plan):
        raise HTTPException(
            status_code=402,
            detail={"reason": "plan", "feature": "code_export", "plan": plan},
        )


def may_export_code(request: Request) -> bool:
    """Whether this caller gets the *whole* generated file (`/codegen`), or only a preview.

    The non-raising sibling of `require_code_export`, and the difference is deliberate:
    `/parse` is an action a user takes, so refusing it with a 402 is the honest answer, while
    `/codegen` always answers — an unentitled caller simply gets the first few lines. Nobody
    should meet an error page for opening a tab.

    So a missing user, a bad internal key, or a DB hiccup all resolve to "preview" rather than
    an exception. Same dev/CI carve-out as `require_code_export`: with no internal key set,
    everyone is entitled, because every request there is the shared `free` dev workspace and
    truncating it would break local dev and the e2e suite."""
    if not settings.internal_key:
        return True
    try:
        with SessionLocal() as session:
            # Shares `_resolve_workspace_id` with the authenticated routes rather than
            # re-implementing it — the difference is only what happens when it says no. It
            # raises (401) on a bad key or a missing user; here that means "preview".
            workspace_id = _resolve_workspace_id(request, session)
            plan = session.execute(
                text(_PLAN_FOR_WORKSPACE), {"id": str(workspace_id)}
            ).scalar_one_or_none()
    except Exception:
        log.info("code-export entitlement unresolved; serving a preview", exc_info=True)
        return False  # fail closed: a bad key or a DB blip must not hand out the paid file
    return entitlements.has_roundtrip(plan)
