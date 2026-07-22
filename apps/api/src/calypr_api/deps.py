"""Per-request tenant resolution.

The public API can't trust a raw user-id header from the internet, so when `CALYPR_INTERNAL_KEY`
is set the Next proxy must present it (`X-Calypr-Internal-Key`) alongside `X-Calypr-User-Id`; the
API then maps that user to their personal workspace via the `resolve_workspace()` SQL function and
scopes the session to it (the RLS GUC). With no key set (local / CI / E2E), every request falls
back to the shared dev workspace — so existing tests keep working unchanged.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from calypr_api import entitlements
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.session import SessionLocal, get_session, set_tenant


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
    proxy must present it plus the user id, which is mapped to a workspace via SQL."""
    if not settings.internal_key:
        return uuid.UUID(DEV_WORKSPACE_ID)
    if request.headers.get("x-calypr-internal-key") != settings.internal_key:
        raise HTTPException(status_code=401, detail="unauthorized")
    user_id = request.headers.get("x-calypr-user-id")
    if not user_id:
        raise HTTPException(status_code=401, detail="missing user")
    resolved = session.execute(
        text("SELECT resolve_workspace(:uid)"), {"uid": user_id}
    ).scalar_one()
    return uuid.UUID(str(resolved))


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
                text("SELECT resolve_workspace(:uid)"), {"uid": user_id}
            ).scalar_one()
        return uuid.UUID(str(resolved))
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
            text("SELECT plan FROM workspace WHERE id = :id"), {"id": str(workspace_id)}
        ).scalar_one_or_none()
    if not entitlements.has_roundtrip(plan):
        raise HTTPException(
            status_code=402,
            detail={"reason": "plan", "feature": "code_export", "plan": plan},
        )
