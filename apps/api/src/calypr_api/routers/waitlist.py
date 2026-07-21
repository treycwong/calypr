"""Waitlist capture + the admin path that promotes an address into the beta.

`POST /waitlist` is public and pre-signup, so it is the one route with no tenant scoping. It is
**write-only by construction** — it returns 204 and never a body — so it can't be used to
enumerate who has signed up. Reading the list requires the admin token.
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from calypr_api import entitlements
from calypr_api.db.models import Waitlist, Workspace
from calypr_api.db.session import get_session
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import (
    InviteRequest,
    InviteResult,
    PlanUpdate,
    WaitlistEntry,
    WaitlistJoin,
)

router = APIRouter()


def _normalize(email: str) -> str:
    """Trim + lowercase so `Ada@Example.com ` and `ada@example.com` are one signup."""
    return email.strip().lower()


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    """Guard for the operator-only routes.

    Fails **closed**: with `CALYPR_ADMIN_TOKEN` unset (the default, including CI and any
    accidental deploy) these routes 404 rather than being open. 404 rather than 403 so their
    existence isn't advertised."""
    expected = os.getenv("CALYPR_ADMIN_TOKEN", "")
    if not expected or x_admin_token != expected:
        raise HTTPException(status_code=404, detail="not found")


@router.post("/waitlist", status_code=status.HTTP_204_NO_CONTENT, tags=["waitlist"])
def join_waitlist(body: WaitlistJoin, session: Session = Depends(get_session)) -> Response:
    """Record an email. Idempotent: submitting twice is a no-op, not a 409 — a duplicate is a
    user pressing the button again, not an error worth surfacing."""
    email = _normalize(body.email)
    existing = session.scalar(select(Waitlist).where(Waitlist.email == email))
    if existing is None:
        session.add(Waitlist(email=email, source=body.source or "landing"))
        session.commit()
        posthog_client.capture("waitlist_joined", properties={"source": body.source or "landing"})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/invite", response_model=InviteResult, tags=["admin"])
def invite_emails(
    body: InviteRequest,
    _: None = Depends(require_admin),
    session: Session = Depends(get_session),
) -> InviteResult:
    """Add addresses to the beta invite list.

    The list *is* `waitlist` rows with `invited_at` set, so this stamps existing signups and
    creates rows for people who never joined the waitlist (`source="invite"`). Once stamped, the
    next time that person signs in their workspace flips to `beta` on its own — no workspace ids
    to look up. Already-invited addresses are left alone, so re-running is safe."""
    invited: list[str] = []
    already: list[str] = []
    for raw in body.emails:
        email = _normalize(raw)
        if not email:
            continue
        entry = session.scalar(select(Waitlist).where(Waitlist.email == email))
        if entry is None:
            session.add(Waitlist(email=email, source="invite", invited_at=func.now()))
            invited.append(email)
        elif entry.invited_at is None:
            entry.invited_at = func.now()
            invited.append(email)
        else:
            already.append(email)
    session.commit()
    if invited:
        posthog_client.capture("beta_invites_sent", properties={"count": len(invited)})
    return InviteResult(invited=invited, already_invited=already)


@router.get("/admin/waitlist", response_model=list[WaitlistEntry], tags=["admin"])
def list_waitlist(
    _: None = Depends(require_admin), session: Session = Depends(get_session)
) -> list[WaitlistEntry]:
    rows = session.scalars(select(Waitlist).order_by(Waitlist.created_at.desc())).all()
    return [
        WaitlistEntry(
            email=r.email,
            source=r.source,
            created_at=r.created_at,
            invited_at=r.invited_at,
        )
        for r in rows
    ]


@router.post("/admin/workspaces/{workspace_id}/plan", tags=["admin"])
def set_workspace_plan(
    workspace_id: uuid.UUID,
    body: PlanUpdate,
    _: None = Depends(require_admin),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    """Move a workspace between tiers — how a design partner gets into the beta.

    Deliberately an operator endpoint with no UI: the closed beta is ~10–25 partners, so a
    curl is the right amount of machinery. Stamps `waitlist.invited_at` when the owner's email
    is on the list, so "who did we let in, and when" stays answerable."""
    if not entitlements.is_valid_plan(body.plan):
        raise HTTPException(
            status_code=422, detail=f"plan must be one of {list(entitlements.PLANS)}"
        )
    ws = session.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")

    ws.plan = body.plan
    if body.email:
        entry = session.scalar(select(Waitlist).where(Waitlist.email == _normalize(body.email)))
        if entry is not None and entry.invited_at is None:
            entry.invited_at = func.now()
    session.commit()

    posthog_client.capture(
        "workspace_plan_changed",
        distinct_id=str(workspace_id),
        properties={"plan": body.plan},
    )
    return {"id": str(ws.id), "plan": ws.plan}
