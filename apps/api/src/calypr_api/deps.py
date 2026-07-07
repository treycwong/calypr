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


def assist_workspace(request: Request) -> uuid.UUID:
    """Workspace id for a compute-only assist call, WITHOUT requiring a DB session in dev/CI.

    The assistant persists nothing in v1 (metering is deferred, §8), so unlike the data
    routes it doesn't need `tenant`'s session + RLS — it only needs the workspace id to scope
    the daily cap. In dev/CI that's the shared dev workspace, resolved with no DB, so the
    assistant works in DB-less local dev (matching `/runs` and start.sh's promise). When
    assist usage starts persisting, switch this back to the full `tenant` dep."""
    if not settings.internal_key:
        return uuid.UUID(DEV_WORKSPACE_ID)
    with SessionLocal() as session:
        return _resolve_workspace_id(request, session)
