"""BYO provider keys: the /provider-keys CRUD surface + vault resolution.

The list-shape assertion is DB-free; the encrypt/store/decrypt round trip and the write-only
guarantee are DB-backed (skipped without Postgres, run in CI), following `test_share.py`.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.session import engine
from calypr_api.main import app
from calypr_api.provider_keys import resolve_model_keys, resolve_tool_keys
from calypr_dsl import GraphSpec, NodeSpec
from fastapi.testclient import TestClient
from sqlalchemy import text

client = TestClient(app)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytest_db = pytest.mark.skipif(not _db_available(), reason="Postgres not available")


def test_resolve_is_empty_without_db_or_keys():
    # DB-free safety: resolution never raises, so a run always proceeds on the env key.
    keys = resolve_model_keys(uuid.UUID(DEV_WORKSPACE_ID))
    assert isinstance(keys, dict)


@pytest_db
def test_set_list_resolve_delete_never_leaks_the_key():
    """Only asserts on the provider it owns. It shares the dev workspace with the developer's
    real Settings → API Keys state, so a `has_key is False` assertion on a bystander provider
    fails as soon as a real key is saved — and failing before the delete below used to leak a
    junk `sk-byo-*` key into the workspace, which then broke unrelated runs."""
    ws = uuid.UUID(DEV_WORKSPACE_ID)
    try:
        # set
        r = client.put("/provider-keys/openai", json={"key": "sk-byo-secret"})
        assert r.status_code == 200 and r.json() == {"provider": "openai", "has_key": True}
        # list reports has_key but never the value
        listed = client.get("/provider-keys")
        assert listed.status_code == 200
        by_provider = {p["provider"]: p["has_key"] for p in listed.json()}
        assert by_provider["openai"] is True
        assert "sk-byo-secret" not in listed.text
        # resolve decrypts server-side
        assert resolve_model_keys(ws).get("openai") == "sk-byo-secret"
        # upsert replaces
        client.put("/provider-keys/openai", json={"key": "sk-byo-rotated"})
        assert resolve_model_keys(ws)["openai"] == "sk-byo-rotated"
        # delete → gone (runs fall back to env)
        assert client.delete("/provider-keys/openai").status_code == 204
        assert "openai" not in resolve_model_keys(ws)
    finally:
        # A mid-test failure must not leave a bogus key behind for the next run.
        client.delete("/provider-keys/openai")


def _unsplash_graph(provider: str = "images_unsplash") -> GraphSpec:
    return GraphSpec(
        id="g",
        name="g",
        nodes=[NodeSpec(id="tools", type="tool", config={"provider": provider})],
        edges=[],
        entry="tools",
    )


def test_resolve_tool_keys_no_ops_without_a_key(monkeypatch):
    """Keyless is the canvas default: the graph comes back untouched (never `api_key: None`),
    so the Unsplash tool falls through to its deterministic stub instead of failing the run.

    The vault lookup is stubbed rather than left to hit the dev workspace: this shares that
    workspace with the developer's real Settings → API Keys state, so a "no key on file"
    assertion starts failing the moment an actual Unsplash key is saved — the same trap
    `test_set_list_resolve_delete_never_leaks_the_key` documents below."""
    monkeypatch.setattr("calypr_api.provider_keys.resolve_model_keys", lambda _ws: {})
    graph = _unsplash_graph()
    out = resolve_tool_keys(graph, uuid.UUID(DEV_WORKSPACE_ID))
    assert out.nodes[0].config.get("api_key", "") == ""


def test_resolve_tool_keys_ignores_other_providers(monkeypatch):
    monkeypatch.setattr(
        "calypr_api.provider_keys.resolve_model_keys", lambda _ws: {"unsplash": "k-1"}
    )
    graph = _unsplash_graph("demo_search")
    out = resolve_tool_keys(graph, uuid.UUID(DEV_WORKSPACE_ID))
    assert "api_key" not in out.nodes[0].config  # untouched — no DB round trip either


def test_resolve_tool_keys_injects_the_vault_key(monkeypatch):
    monkeypatch.setattr(
        "calypr_api.provider_keys.resolve_model_keys", lambda _ws: {"unsplash": "k-1"}
    )
    out = resolve_tool_keys(_unsplash_graph(), uuid.UUID(DEV_WORKSPACE_ID))
    assert out.nodes[0].config["api_key"] == "k-1"


@pytest_db
def test_unsplash_key_round_trips():
    """Unsplash is a *tool* key rather than a model key, but rides the same vault surface."""
    ws = uuid.UUID(DEV_WORKSPACE_ID)
    try:
        r = client.put("/provider-keys/unsplash", json={"key": "unsplash-secret"})
        assert r.status_code == 200 and r.json() == {"provider": "unsplash", "has_key": True}
        graph = resolve_tool_keys(_unsplash_graph(), ws)
        assert graph.nodes[0].config["api_key"] == "unsplash-secret"
        assert client.delete("/provider-keys/unsplash").status_code == 204
    finally:
        client.delete("/provider-keys/unsplash")


@pytest_db
def test_unknown_provider_is_rejected():
    assert client.put("/provider-keys/bogus", json={"key": "x"}).status_code == 404


@pytest_db
def test_empty_key_is_rejected():
    assert client.put("/provider-keys/openai", json={"key": "  "}).status_code == 422
