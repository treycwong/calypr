"""Resolve a workspace's BYO model API keys from the vault, for run-time injection.

Mirrors `connectors.resolve_graph`: opens a short-lived RLS-scoped session, decrypts each
stored provider key server-side, and returns a `{provider: key}` map the model factory uses to
override the server env per provider. No-ops (and never fails a run) when the DB is unreachable
or the workspace has no keys — so BYO-key is purely additive over the env-key default."""

from __future__ import annotations

import logging
import uuid

from calypr_dsl import GraphSpec
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
                session.execute(select(ProviderKey).where(ProviderKey.workspace_id == workspace_id))
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


#: Tool-node providers that run on a workspace's BYO key, mapped to the provider-key row that
#: holds it. A Tool node whose provider is listed here gets `api_key` injected just before
#: compile; without a key the tool falls back to its deterministic stub (see `tools_catalog`).
_TOOL_KEY_PROVIDERS = {"images_unsplash": "unsplash", "tavily": "tavily"}


def resolve_tool_keys(graph: GraphSpec, workspace_id: uuid.UUID) -> GraphSpec:
    """Return a copy of `graph` with each key-backed Tool node's `api_key` filled from the vault.

    Same contract as `connectors.resolve_graph`: the DSL only ever carries the provider name, the
    secret is decrypted server-side at run time, and a graph with no such node (or an unreachable
    DB) is returned untouched rather than failing the run — the tool then serves stub results."""
    wanted = {
        _TOOL_KEY_PROVIDERS[p]
        for n in graph.nodes
        if n.type == "tool" and (p := n.config.get("provider")) in _TOOL_KEY_PROVIDERS
    }
    if not wanted:
        return graph
    keys = {k: v for k, v in resolve_model_keys(workspace_id).items() if k in wanted}
    if not keys:
        return graph
    nodes = []
    for n in graph.nodes:
        provider = n.config.get("provider") if n.type == "tool" else None
        key = keys.get(_TOOL_KEY_PROVIDERS.get(provider or "", ""))
        nodes.append(n.model_copy(update={"config": {**n.config, "api_key": key}}) if key else n)
    return graph.model_copy(update={"nodes": nodes})
