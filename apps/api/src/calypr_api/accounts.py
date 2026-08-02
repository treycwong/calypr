"""Getting from a request's workspace to the account that pays for it, and counting what that
account has used.

The request resolves to a *workspace* (that's what the RLS GUC scopes to), but every quota is an
*account* question — projects, workspaces, credits and storage all pool across the workspaces one
account owns. These three functions are that hop, in one place, so routers don't each hand-write
the join and quietly disagree about whether a limit is pooled.

**These counts deliberately reach outside the request's workspace**, which works today because
the app connects as the table owner and therefore bypasses RLS (0001_baseline calls a dedicated
non-owner app role "a later phase"). If that phase ever lands, the `workspace` and `agent`
policies would clip both counts to the current workspace — `workspace_count` would always return
1 and `project_count` would stop being pooled, so **the caps would silently stop biting rather
than fail loudly.** Whoever introduces that role needs to move these two queries to SECURITY
DEFINER functions, the way `list_account_workspaces` already is for the same reason.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from calypr_api.db.models import Account, Agent, Workspace


def account_for_workspace(session: Session, workspace_id: uuid.UUID) -> Account | None:
    """The account owning this workspace, or None if the workspace is unknown.

    None is a real answer, not just an error case: `run_workspace` hands back the shared dev
    workspace for anonymous traffic, and callers treat "no account" as "not subject to plan
    limits" rather than refusing the request."""
    return session.scalar(
        select(Account).join(Workspace, Workspace.account_id == Account.id).where(
            Workspace.id == workspace_id
        )
    )


def project_count(session: Session, account_id: uuid.UUID) -> int:
    """Saved agents across **all** of this account's workspaces.

    Pooled on purpose: the cap is "20 projects", not "20 per workspace". Counting per workspace
    would make a second workspace a way to buy more projects for free."""
    return int(
        session.scalar(
            select(func.count(Agent.id))
            .join(Workspace, Workspace.id == Agent.workspace_id)
            .where(Workspace.account_id == account_id)
        )
        or 0
    )


def workspace_count(session: Session, account_id: uuid.UUID) -> int:
    return int(
        session.scalar(
            select(func.count(Workspace.id)).where(Workspace.account_id == account_id)
        )
        or 0
    )
