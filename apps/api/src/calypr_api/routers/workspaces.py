"""Workspace CRUD, the switcher's list, and the account-level usage the Usage tab renders.

Split out of `agents.py`, which was already carrying agents, share links *and* workspace config.

Two things here are unlike the rest of the API. **`GET /workspaces` cannot use the request's
tenant session** — `workspace`'s RLS policy shows exactly the one workspace the GUC names, which
is the wrong answer when the whole point is to list the others; it goes through the
`list_account_workspaces` SECURITY DEFINER function instead. And **the caps are enforced here but
counted on the account**, because projects and workspaces pool across everything one account
owns.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import delete, select, text

from calypr_api import accounts, credits, entitlements
from calypr_api.assistant_models import is_allowed
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import Workspace
from calypr_api.deps import Tenant, tenant
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import (
    AccountUsage,
    CreditUsage,
    PlanLimits,
    WorkspaceCreate,
    WorkspaceInfo,
    WorkspaceSummary,
    WorkspaceUpdate,
)

router = APIRouter(tags=["workspace"])


def _limits_of(plan: str | None) -> PlanLimits:
    lim = entitlements.limits(plan)
    return PlanLimits(
        projects=lim.projects,
        workspaces=lim.workspaces,
        monthly_credits=lim.monthly_credits,
        storage_bytes=lim.storage_bytes,
    )


def _info(t: Tenant, ws: Workspace) -> WorkspaceInfo:
    """The full workspace payload: the workspace's own fields plus its account's entitlements."""
    account = accounts.account_for_workspace(t.session, ws.id)
    plan = account.plan if account else entitlements.FREE
    usage = AccountUsage()
    credit_usage = CreditUsage()
    if account is not None:
        usage = AccountUsage(
            projects=accounts.project_count(t.session, account.id),
            workspaces=accounts.workspace_count(t.session, account.id),
            storage_bytes=account.storage_bytes,
            storage_measured_at=account.storage_measured_at,
        )
        credit_usage = CreditUsage(**credits.usage_summary(t.session, account))
    return WorkspaceInfo(
        id=str(ws.id),
        name=ws.name,
        account_id=str(account.id) if account else "",
        plan=plan,
        signed_in_as=t.email,
        assistant_model=ws.assistant_model,
        default_model=ws.default_model,
        credits=credit_usage,
        limits=_limits_of(plan),
        usage=usage,
    )


@router.get("/workspaces", response_model=list[WorkspaceSummary])
def list_workspaces(request: Request, t: Tenant = Depends(tenant)) -> list[WorkspaceSummary]:
    """Every workspace this account owns — what the sidebar switcher renders.

    In dev/CI (no internal key) there is no user to resolve, and every request is the shared dev
    workspace; return that single row rather than an empty list so the switcher still renders
    offline, per `start.sh`'s DB-less promise."""
    user_id = request.headers.get("x-calypr-user-id")
    if not settings.internal_key or not user_id:
        ws = t.session.get(Workspace, t.workspace_id)
        return [
            WorkspaceSummary(
                id=str(t.workspace_id),
                name=ws.name if ws else "Dev Workspace",
                created_at=ws.created_at if ws else None,
                is_current=True,
            )
        ]
    rows = t.session.execute(
        text("SELECT id, name, created_at FROM list_account_workspaces(:uid)"),
        {"uid": user_id},
    ).all()
    return [
        WorkspaceSummary(
            id=str(row.id),
            name=row.name,
            created_at=row.created_at,
            is_current=row.id == t.workspace_id,
        )
        for row in rows
    ]


@router.post("/workspaces", response_model=WorkspaceInfo, status_code=201)
def create_workspace(body: WorkspaceCreate, t: Tenant = Depends(tenant)) -> WorkspaceInfo:
    """Create a workspace on the caller's account, subject to the plan's workspace cap."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="name is required")

    account = accounts.account_for_workspace(t.session, t.workspace_id)
    if account is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    lim = entitlements.limits(account.plan)
    # Same dev/CI carve-out every other gate uses: with no internal key every request is the
    # shared dev workspace, so enforcing here would only break local dev and the e2e suite.
    #
    # Racy by a bounded amount: two concurrent creates can both read a count one below the cap
    # and both succeed. Worst case is one workspace over, self-corrects on the next create, and
    # is not worth a lock on a path someone hits a handful of times ever.
    if settings.internal_key:
        used = accounts.workspace_count(t.session, account.id)
        if used >= lim.workspaces:
            raise HTTPException(
                status_code=402,
                detail={
                    "reason": "workspace_cap",
                    "limit": lim.workspaces,
                    "used": used,
                    "plan": account.plan,
                    "message": (
                        f"You've used {used} of {lim.workspaces} "
                        f"workspace{'s' if lim.workspaces != 1 else ''} on "
                        f"{account.plan.title()}."
                    ),
                },
            )

    ws = Workspace(account_id=account.id, name=name)
    t.session.add(ws)
    t.session.commit()
    t.session.refresh(ws)
    posthog_client.capture(
        "workspace_created",
        distinct_id=str(account.id),
        properties={"account_id": str(account.id), "workspace_id": str(ws.id)},
    )
    return _info(t, ws)


@router.delete("/workspaces/{workspace_id}", status_code=204)
def delete_workspace(workspace_id: uuid.UUID, t: Tenant = Depends(tenant)) -> None:
    """Delete a workspace and everything in it.

    Refuses the last one: an account with no workspace has nowhere to put work, and
    `resolve_account` would simply recreate a 'Personal' one on the next request — so allowing
    it would look like a broken delete rather than a delete.

    Exists because without it, hitting the workspace cap would be unrecoverable."""
    account = accounts.account_for_workspace(t.session, t.workspace_id)
    if account is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    # Ownership is checked in the predicate, because the tenant GUC can't do it here: `workspace`
    # RLS shows only the *current* workspace, so an ORM `get()` would return None for every other
    # one and make deleting anything but the one you're in impossible. Scoping the DELETE to
    # `account_id` is what keeps someone else's workspace out of reach — the id is supplied by
    # the caller rather than resolved from their identity, so it is not trustworthy on its own.
    if accounts.workspace_count(t.session, account.id) <= 1:
        # Checked before existence so deleting your only workspace says *why* rather than 404ing.
        if t.session.scalar(
            select(Workspace.id).where(
                Workspace.id == workspace_id, Workspace.account_id == account.id
            )
        ):
            raise HTTPException(status_code=400, detail="cannot delete your only workspace")

    deleted = t.session.execute(
        delete(Workspace)
        .where(Workspace.id == workspace_id, Workspace.account_id == account.id)
        .execution_options(synchronize_session=False)
    ).rowcount  # cascades agents, runs, share links, connectors, uploads
    if not deleted:
        raise HTTPException(status_code=404, detail="workspace not found")
    t.session.commit()
    posthog_client.capture(
        "workspace_deleted",
        distinct_id=str(account.id),
        properties={"account_id": str(account.id), "workspace_id": str(workspace_id)},
    )


@router.get("/workspaces/current", response_model=WorkspaceInfo)
def get_current_workspace(t: Tenant = Depends(tenant)) -> WorkspaceInfo:
    ws = t.session.get(Workspace, t.workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    # Redeem a beta invite here rather than on every request: the client asks for its workspace
    # once per page load, and this is exactly when it needs to know what it's entitled to.
    account = accounts.account_for_workspace(t.session, ws.id)
    if account is not None and entitlements.grant_beta_if_invited(t.session, account, t.email):
        t.session.commit()
        posthog_client.capture(
            "beta_access_granted",
            distinct_id=str(account.id),
            properties={"account_id": str(account.id)},
        )
    return _info(t, ws)


@router.patch("/workspaces/current", response_model=WorkspaceInfo)
def update_workspace(body: WorkspaceUpdate, t: Tenant = Depends(tenant)) -> WorkspaceInfo:
    """Partial update of the current workspace (name and/or models).

    All three fields are still the *workspace's* — a user with several workspaces can point each
    at a different default model. Only money moved to the account."""
    ws = t.session.get(Workspace, t.workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    if body.name is not None:
        ws.name = body.name
    if body.assistant_model is not None:
        # Allow-listed: this value is persisted and later handed to the model factory, so an
        # arbitrary string here would point the assistant at an unpriced model.
        if not is_allowed(body.assistant_model):
            raise HTTPException(status_code=422, detail="unsupported assistant model")
        ws.assistant_model = body.assistant_model
    if body.default_model is not None:
        # Same allow-list as the assistant: this value is persisted and later handed to the
        # model factory for every node that inherits, so an arbitrary string here would point
        # the whole canvas at an unpriced model.
        if not is_allowed(body.default_model):
            raise HTTPException(status_code=422, detail="unsupported default model")
        ws.default_model = body.default_model
    t.session.commit()
    posthog_client.capture(
        "workspace_updated",
        distinct_id=str(t.workspace_id),
        properties={
            "workspace_id": str(t.workspace_id),
            "renamed": body.name is not None,
            "assistant_model": body.assistant_model,
            "default_model": body.default_model,
        },
    )
    return _info(t, ws)


@router.get("/usage", response_model=WorkspaceInfo)
def get_usage(t: Tenant = Depends(tenant)) -> WorkspaceInfo:
    """What the Usage tab renders: credits, projects, workspaces and storage against the caps.

    Deliberately the same payload as `/workspaces/current` rather than a narrower one — it is the
    same numbers, and two shapes that must agree is how they stop agreeing."""
    ws = t.session.get(Workspace, t.workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return _info(t, ws)


# The dev workspace is exempt from every cap, matching `credits.check_can_run` — anonymous
# production traffic lands there, and metering it would let the first visitor exhaust it for
# everyone.
_UNCAPPED = {DEV_WORKSPACE_ID}


def enforce_project_cap(t: Tenant) -> None:
    """402 if this account has no project slots left. Called by `create_agent`.

    Pooled across the account's workspaces: the cap is "20 projects", not "20 per workspace",
    so a second workspace organises work rather than buying more of it.

    Same bounded race as the workspace cap — two concurrent creates can both pass. One project
    over is not worth serialising every create."""
    if not settings.internal_key or str(t.workspace_id) in _UNCAPPED:
        return
    account = accounts.account_for_workspace(t.session, t.workspace_id)
    if account is None:
        return
    lim = entitlements.limits(account.plan)
    used = accounts.project_count(t.session, account.id)
    if used < lim.projects:
        return
    raise HTTPException(
        status_code=402,
        detail={
            "reason": "project_cap",
            "limit": lim.projects,
            "used": used,
            "plan": account.plan,
            "message": (
                f"You've used {used} of {lim.projects} "
                f"{'free ' if account.plan == entitlements.FREE else ''}projects."
            ),
        },
    )
