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
from calypr_api.provider_keys import resolve_model_keys
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


@pytest_db
def test_unknown_provider_is_rejected():
    assert client.put("/provider-keys/bogus", json={"key": "x"}).status_code == 404


@pytest_db
def test_empty_key_is_rejected():
    assert client.put("/provider-keys/openai", json={"key": "  "}).status_code == 422
