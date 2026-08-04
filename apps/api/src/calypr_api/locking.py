"""What a downgraded account may still *do* with what it already has.

Capacity caps are enforced when you create something — `create_workspace`, `enforce_project_cap`.
That answers "may I make another?" and nothing else, which leaves a gap the moment a plan gets
*smaller*: a lapsed Plus account keeps three workspaces and twenty projects and can go on working
in all of them forever. One month of Plus buys the capacity permanently.

The answer here is to lock the excess rather than delete it. **A downgrade takes back capacity,
never data** — capacity is recoverable by re-subscribing, and anything deleted is not. So
everything over the cap becomes read-only: still there, still readable, still exportable by
deleting down to the cap or upgrading, but no new work goes into it.

**Which ones lock: the newest over the cap.** Ranked by `created_at`, keep the first N. Oldest-
first is already how `resolve_workspace` picks a default and how `list_account_workspaces`
orders, so "your original workspace still works" is both consistent with the rest of the system
and what someone would guess without being told.

**Nothing is stored.** Locked-ness is derived from the plan and the row's rank, every time. A
stored flag would need updating on every plan change, every create and every delete, and the one
that drifted would be the one deciding whether to refuse a request.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from calypr_api import accounts, entitlements
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.session import SessionLocal
from calypr_api.deps import Tenant

log = logging.getLogger(__name__)

#: Never locked, matching `enforce_project_cap`: anonymous production traffic lands on the dev
#: workspace, and locking it would break every visitor at once.
_UNLOCKABLE = {DEV_WORKSPACE_ID}


def _over_cap_ids(session: Session, table: str, account_id: uuid.UUID, cap: int) -> set[uuid.UUID]:
    """Ids of this account's `table` rows ranked beyond `cap`, oldest kept.

    `id` breaks ties in the ordering so two rows created in the same instant can't swap places
    between calls — a lock that moved around under a user would be worse than either answer.
    """
    join = "" if table == "workspace" else " JOIN workspace w ON w.id = t.workspace_id"
    owner = "t.account_id" if table == "workspace" else "w.account_id"
    rows = session.execute(
        text(
            f"""
            SELECT id FROM (
              SELECT t.id, row_number() OVER (ORDER BY t.created_at, t.id) AS rn
                FROM {table} t{join}
               WHERE {owner} = :acc
            ) ranked
             WHERE rn > :cap
            """  # noqa: S608 - `table` is a literal from this module, never user input
        ),
        {"acc": str(account_id), "cap": cap},
    ).all()
    return {r[0] for r in rows}


def locked_workspace_ids(session: Session, account_id: uuid.UUID, plan: str) -> set[uuid.UUID]:
    return _over_cap_ids(session, "workspace", account_id, entitlements.limits(plan).workspaces)


def locked_agent_ids(session: Session, account_id: uuid.UUID, plan: str) -> set[uuid.UUID]:
    return _over_cap_ids(session, "agent", account_id, entitlements.limits(plan).projects)


@dataclass(frozen=True)
class LockedIds:
    """Everything locked on one account, fetched once."""

    workspaces: frozenset[uuid.UUID] = frozenset()
    agents: frozenset[uuid.UUID] = frozenset()


def locked_ids_for_request(t: Tenant) -> LockedIds:
    """Both lock sets for the caller's account, for rendering rather than refusing.

    List endpoints need the answer for every row, and asking per row would turn one page render
    into N queries for a value that is identical across all of them. Empty under the same
    carve-outs as the gates, so dev/CI shows nothing locked."""
    account = _account_and_plan(t)
    if account is None:
        return LockedIds()
    return LockedIds(
        workspaces=frozenset(locked_workspace_ids(t.session, account.id, account.plan)),
        agents=frozenset(locked_agent_ids(t.session, account.id, account.plan)),
    )


def _refuse(kind: str, plan: str) -> HTTPException:
    """The 402 both locks raise.

    Reuses the shape `create_workspace` and `enforce_project_cap` already emit, so the web's
    `CapReachedError` parses it without a new branch. `reason` distinguishes it from those two:
    this isn't "you can't make another", it's "this one is read-only until you're back under the
    cap" — a different sentence with a different remedy."""
    lim = entitlements.limits(plan)
    allowed = lim.workspaces if kind == "workspace" else lim.projects
    return HTTPException(
        status_code=402,
        detail={
            "reason": "locked",
            "kind": kind,
            "limit": allowed,
            "plan": plan,
            "message": (
                f"This {kind} is read-only: {plan.title()} includes "
                f"{allowed} {kind}{'s' if allowed != 1 else ''}, and this one is beyond that. "
                f"Upgrade, or delete down to {allowed} to unlock it."
            ),
        },
    )


def _account_and_plan(t: Tenant):
    """The caller's account, or None when locking doesn't apply at all.

    The carve-outs mirror `enforce_project_cap` exactly: no internal key means dev/CI, where every
    request is the shared dev workspace and enforcing would break local dev and the e2e suite
    while protecting nothing."""
    if not settings.internal_key or str(t.workspace_id) in _UNLOCKABLE:
        return None
    return accounts.account_for_workspace(t.session, t.workspace_id)


def require_unlocked_workspace(t: Tenant) -> None:
    """402 if the request's workspace is beyond the plan's cap. For writes only."""
    account = _account_and_plan(t)
    if account is None:
        return
    if t.workspace_id in locked_workspace_ids(t.session, account.id, account.plan):
        raise _refuse("workspace", account.plan)


def locked_run_message(workspace_id: uuid.UUID) -> str | None:
    """Why a run may not start in this workspace, or None if it may.

    The variant for `/runs` and `/assist`, which resolve to a bare workspace id and hold no
    session — and which stream their refusals in-band rather than raising, because the response
    has already begun. Mirrors `run_access.check_run_gates`'s shape for that reason.

    **Fails open**, deliberately and consistently with every other gate on this path: a database
    hiccup must not stop people working. The cost of being wrong is one run in a workspace that
    should have been read-only; the cost of failing closed is an outage that looks like a billing
    problem."""
    if not settings.internal_key or str(workspace_id) in _UNLOCKABLE:
        return None
    try:
        with SessionLocal() as session:
            account = accounts.account_for_workspace(session, workspace_id)
            if account is None:
                return None
            if workspace_id not in locked_workspace_ids(session, account.id, account.plan):
                return None
            allowed = entitlements.limits(account.plan).workspaces
    except Exception:
        log.warning("workspace lock check failed — allowing the run", exc_info=True)
        return None
    return (
        f"This workspace is read-only. {account.plan.title()} includes "
        f"{allowed} workspace{'s' if allowed != 1 else ''}, and this one is beyond that — "
        f"upgrade, or delete down to {allowed} to start running here again."
    )


def require_unlocked_agent(t: Tenant, agent_id: uuid.UUID | str) -> None:
    """402 if this project is beyond the plan's cap, **or** its workspace is.

    Both, because a project inside a locked workspace is unreachable for new work regardless of
    its own rank — checking only the project would leave a writable island in a read-only
    workspace."""
    account = _account_and_plan(t)
    if account is None:
        return
    if t.workspace_id in locked_workspace_ids(t.session, account.id, account.plan):
        raise _refuse("workspace", account.plan)
    if uuid.UUID(str(agent_id)) in locked_agent_ids(t.session, account.id, account.plan):
        raise _refuse("project", account.plan)
