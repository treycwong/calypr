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
from calypr_api.db.session import get_session, set_tenant


@dataclass
class Tenant:
    """The resolved workspace for a request, plus the session scoped to it."""

    session: Session
    workspace_id: uuid.UUID


def tenant(request: Request, session: Session = Depends(get_session)) -> Tenant:
    if not settings.internal_key:
        ws = uuid.UUID(DEV_WORKSPACE_ID)  # dev / CI: single shared workspace
    else:
        if request.headers.get("x-calypr-internal-key") != settings.internal_key:
            raise HTTPException(status_code=401, detail="unauthorized")
        user_id = request.headers.get("x-calypr-user-id")
        if not user_id:
            raise HTTPException(status_code=401, detail="missing user")
        resolved = session.execute(
            text("SELECT resolve_workspace(:uid)"), {"uid": user_id}
        ).scalar_one()
        ws = uuid.UUID(str(resolved))
    set_tenant(session, str(ws))
    return Tenant(session=session, workspace_id=ws)
