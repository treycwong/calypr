"""Read a workspace's own settings off the hot path, without failing the request.

Same contract as `provider_keys.resolve_model_keys`: a short-lived RLS-scoped session, and any
DB problem degrades to the default rather than erroring — a workspace preference must never be
the reason `/assist` stops working.
"""

from __future__ import annotations

import logging
import uuid

from calypr_api.assistant_models import is_allowed
from calypr_api.db.models import Workspace
from calypr_api.db.session import SessionLocal, set_tenant

log = logging.getLogger("calypr_api")


def workspace_assistant_model(workspace_id: uuid.UUID) -> str:
    """The workspace's chosen assistant model, or "" to fall back to the server default.

    Returns "" for an unknown/removed model id too, so pulling an entry out of the allow-list
    silently reverts affected workspaces instead of breaking their assistant."""
    try:
        with SessionLocal() as session:
            set_tenant(session, str(workspace_id))
            ws = session.get(Workspace, workspace_id)
            chosen = (ws.assistant_model if ws else "") or ""
            if chosen and not is_allowed(chosen):
                log.warning("workspace assistant model %r no longer allowed", chosen)
                return ""
            return chosen
    except Exception:
        log.warning("assistant model lookup skipped (DB unavailable)", exc_info=True)
        return ""
