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

from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.session import SessionLocal, get_session, set_tenant


@dataclass
class Tenant:
    """The resolved workspace for a request, plus the session scoped to it."""

    session: Session
    workspace_id: uuid.UUID


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
    return Tenant(session=session, workspace_id=ws)


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
