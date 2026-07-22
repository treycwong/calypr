"""Connector resolution + the /connectors CRUD surface.

The resolution tests are DB-free (they build a `ConnectorCredential` in memory), asserting the
one security-critical mapping: a stored secret becomes request headers, never leaks into the
response, and the graph only ever carries a handle. The CRUD tests are DB-backed (skipped
without Postgres, run in CI), following the `test_share.py` pattern.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import vault
from calypr_api.config import settings
from calypr_api.connectors import (
    ConnectorResolutionError,
    assert_egress_allowed,
    resolve,
    resolve_graph,
)
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import ConnectorCredential
from calypr_api.db.session import engine
from calypr_api.main import app
from calypr_compiler.templates import mcp_react
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec
from fastapi.testclient import TestClient
from sqlalchemy import text

client = TestClient(app)


# --- DB-free resolution -------------------------------------------------------------------


def test_resolve_mcp_maps_secret_to_bearer_header():
    cred = ConnectorCredential(
        workspace_id=uuid.uuid4(),
        kind="mcp",
        name="my server",
        url="https://example.com/mcp",
        transport="streamable_http",
        secret_encrypted=vault.encrypt("bearer-tok"),
    )
    conn = resolve(cred)
    assert conn.url == "https://example.com/mcp"
    assert conn.headers == {"Authorization": "Bearer bearer-tok"}


def test_resolve_notion_uses_notion_token_header(monkeypatch):
    from calypr_api.config import settings

    monkeypatch.setattr(settings, "notion_mcp_url", "https://notion-mcp.internal/mcp")
    cred = ConnectorCredential(
        workspace_id=uuid.uuid4(),
        kind="notion",
        name="Acme",
        secret_encrypted=vault.encrypt("ntn_bot_token"),
    )
    conn = resolve(cred)
    assert conn.url == "https://notion-mcp.internal/mcp"
    assert conn.headers == {"Notion-Token": "ntn_bot_token"}


def test_egress_guard_blocks_private_hosts_in_production(monkeypatch):
    # SSRF guard: on a real deployment, a Tier B URL resolving to loopback/private is rejected.
    monkeypatch.setattr(settings, "internal_key", "proxy-shared-secret")  # prod signal
    for blocked in (
        "http://localhost:3333/mcp",
        "http://127.0.0.1/mcp",
        "https://10.0.0.5/mcp",
        "https://169.254.169.254/latest/meta-data",  # cloud metadata
    ):
        with pytest.raises(ConnectorResolutionError):
            assert_egress_allowed(blocked)
    # A public host is allowed.
    assert_egress_allowed("https://mcp.example.com/mcp")


def test_egress_guard_is_off_in_local_dev(monkeypatch):
    # No prod signal → localhost is allowed (so dev/CI can test against local MCP servers).
    monkeypatch.setattr(settings, "internal_key", "")
    monkeypatch.setattr(settings, "environment", "development")
    assert_egress_allowed("http://localhost:3333/mcp")  # no raise


def test_resolve_graph_is_a_noop_without_connector_refs():
    graph = mcp_react()  # its tool node has no mcp_connector_ref
    assert resolve_graph(graph, uuid.UUID(DEV_WORKSPACE_ID)) is graph


def test_resolve_graph_leaves_unresolvable_refs_unset():
    # A ref that can't be resolved (no DB / unknown id) must degrade gracefully — the node is
    # left without a URL rather than crashing the run.
    graph = GraphSpec(
        id="g",
        name="g",
        state=[],
        nodes=[
            NodeSpec(
                id="tools",
                type="tool",
                config={"provider": "mcp", "mcp_connector_ref": str(uuid.uuid4())},
            )
        ],
        edges=[EdgeSpec(id="e", source="tools", target="tools")],
        entry="tools",
    )
    resolved = resolve_graph(graph, uuid.UUID(DEV_WORKSPACE_ID))
    tool = next(n for n in resolved.nodes if n.id == "tools")
    assert not tool.config.get("mcp_url")  # unresolved → no URL, node degrades to zero tools


# --- DB-backed CRUD -----------------------------------------------------------------------


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytest_db = pytest.mark.skipif(not _db_available(), reason="Postgres not available")


@pytest_db
def test_create_list_delete_connector_never_returns_secret():
    created = client.post(
        "/connectors",
        json={"name": "test server", "url": "https://localhost:9/mcp", "secret": "s3cr3t"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    cid = body["id"]
    assert body["has_secret"] is True
    assert "secret" not in body and "s3cr3t" not in created.text  # never echoed

    listed = client.get("/connectors")
    assert listed.status_code == 200
    assert any(c["id"] == cid for c in listed.json())
    assert "s3cr3t" not in listed.text

    assert client.delete(f"/connectors/{cid}").status_code == 204
    assert all(c["id"] != cid for c in client.get("/connectors").json())


@pytest_db
def test_create_connector_rejects_non_https_url():
    r = client.post("/connectors", json={"name": "bad", "url": "ftp://evil/mcp"})
    assert r.status_code == 422  # schema validator blocks non-https URLs
