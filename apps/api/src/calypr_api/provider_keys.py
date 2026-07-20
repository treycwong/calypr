"""Resolve a workspace's BYO model API keys from the vault, for run-time injection.

Mirrors `connectors.resolve_graph`: opens a short-lived RLS-scoped session, decrypts each
stored provider key server-side, and returns a `{provider: key}` map the model factory uses to
override the server env per provider. No-ops (and never fails a run) when the DB is unreachable
or the workspace has no keys — so BYO-key is purely additive over the env-key default."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select

from calypr_api.db.models import ProviderKey
from calypr_api.db.session import SessionLocal, set_tenant
from calypr_api.vault import decrypt

log = logging.getLogger("calypr_api")


def resolve_model_keys(workspace_id: uuid.UUID) -> dict[str, str]:
    """The workspace's decrypted provider keys ({provider: api_key}); {} on any DB/vault error."""
    try:
        with SessionLocal() as session:
            set_tenant(session, str(workspace_id))
            rows = (
                session.execute(
                    select(ProviderKey).where(
                        ProviderKey.workspace_id == workspace_id
                    )
                )
                .scalars()
                .all()
            )
            out: dict[str, str] = {}
            for row in rows:
                try:
                    out[row.provider] = decrypt(row.key_encrypted)
                except Exception:  # a single bad row must not sink the whole run
                    log.warning("provider key %s did not decrypt", row.provider)
            return out
    except Exception:
        log.warning("provider key resolution skipped (DB unavailable)", exc_info=True)
        return {}
