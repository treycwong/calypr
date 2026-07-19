"""Connector resolution — turn a saved `connector_credential` row into a live MCP connection.

One place decides how each connector kind maps to a URL + request headers, decrypting the
vault secret server-side. Used by the `/connectors/*/test` probe and by the run path, which
injects the resolved connection into a Tool node's config just before compile (so the DSL only
ever carries a `mcp_connector_ref`, never a token)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from calypr_dsl import GraphSpec
from sqlalchemy import select

from calypr_api.config import settings
from calypr_api.db.models import ConnectorCredential
from calypr_api.db.session import SessionLocal, set_tenant
from calypr_api.vault import decrypt

log = logging.getLogger("calypr_api")


@dataclass
class ResolvedConnection:
    url: str
    transport: str
    headers: dict[str, str] = field(default_factory=dict)


class ConnectorResolutionError(RuntimeError):
    """The connector can't be turned into a live connection (e.g. Notion server URL unset)."""


def resolve(cred: ConnectorCredential) -> ResolvedConnection:
    """Map a connector row to a live MCP connection, decrypting its secret. Never returns the
    secret itself — only the request headers that carry it."""
    secret = decrypt(cred.secret_encrypted) if cred.secret_encrypted else ""
    if cred.kind == "notion":
        if not settings.notion_mcp_url:
            raise ConnectorResolutionError(
                "Notion MCP server URL is not configured (CALYPR_NOTION_MCP_URL)."
            )
        # The self-hosted notion-mcp-server runs with --enable-token-passthrough: each request
        # carries the workspace's Notion bot token via the `Notion-Token` header.
        return ResolvedConnection(
            url=settings.notion_mcp_url,
            transport="streamable_http",
            headers={"Notion-Token": secret} if secret else {},
        )
    # kind == "mcp" (Tier B): the user-supplied URL + optional bearer.
    if not cred.url:
        raise ConnectorResolutionError("connector has no URL")
    return ResolvedConnection(
        url=cred.url,
        transport=cred.transport,
        headers={"Authorization": f"Bearer {secret}"} if secret else {},
    )


def _connector_refs(graph: GraphSpec) -> set[str]:
    """The connector ids referenced by any MCP Tool node in the graph."""
    return {
        ref
        for n in graph.nodes
        if n.type == "tool" and n.config.get("provider") == "mcp"
        and (ref := n.config.get("mcp_connector_ref"))
    }


def resolve_graph(graph: GraphSpec, workspace_id: uuid.UUID) -> GraphSpec:
    """Return a copy of `graph` with every MCP Tool node's `mcp_connector_ref` resolved to a
    live URL + headers, decrypting vault secrets server-side.

    Runs just before compile so the DSL only ever carries a handle. No-ops (and never touches
    the DB) when no node references a connector — keeping DB-less dev/CI runs working. A ref
    that can't be resolved is left unset, so the Tool node degrades gracefully (zero tools →
    the agent answers) rather than crashing the run."""
    refs = _connector_refs(graph)
    if not refs:
        return graph
    resolved: dict[str, ResolvedConnection] = {}
    try:
        with SessionLocal() as session:
            set_tenant(session, str(workspace_id))
            rows = (
                session.execute(
                    select(ConnectorCredential).where(
                        ConnectorCredential.workspace_id == workspace_id,
                        ConnectorCredential.id.in_([uuid.UUID(r) for r in refs]),
                    )
                )
                .scalars()
                .all()
            )
            for row in rows:
                try:
                    resolved[str(row.id)] = resolve(row)
                except ConnectorResolutionError as exc:
                    log.warning("connector %s did not resolve: %s", row.id, exc)
    except Exception:  # DB unreachable / bad id — degrade gracefully, don't break the stream
        log.warning("connector resolution skipped (DB unavailable)", exc_info=True)
        return graph

    nodes = []
    for n in graph.nodes:
        ref = n.config.get("mcp_connector_ref") if n.type == "tool" else None
        conn = resolved.get(ref) if ref else None
        if conn is None:
            nodes.append(n)
            continue
        nodes.append(
            n.model_copy(
                update={
                    "config": {
                        **n.config,
                        "mcp_url": conn.url,
                        "mcp_transport": conn.transport,
                        "mcp_headers": conn.headers,
                    }
                }
            )
        )
    return graph.model_copy(update={"nodes": nodes})
