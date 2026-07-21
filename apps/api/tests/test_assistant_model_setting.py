"""Per-workspace AI-assistant model (Settings → Workspace)."""

import uuid

import pytest
from calypr_api.assistant_models import assistant_model_options, is_allowed
from calypr_api.db.session import engine
from calypr_api.deps import DEV_WORKSPACE_ID
from calypr_api.main import app
from calypr_api.workspace_settings import workspace_assistant_model
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


def test_options_mark_frontier_models_as_byo() -> None:
    by_value = {o.value: o for o in assistant_model_options()}
    assert by_value["kimi-k3"].byo_provider == "moonshot"
    assert by_value["gpt-4o"].byo_provider is None
    # "" is the inherit-the-server-default sentinel and must always be offered.
    assert by_value[""].byo_provider is None


def test_allow_list_rejects_arbitrary_ids() -> None:
    assert is_allowed("kimi-k3")
    assert is_allowed("")
    assert not is_allowed("gpt-4-turbo-o1-preview-expensive")


def test_assistant_models_endpoint_serves_the_picker() -> None:
    r = client.get("/assistant-models")
    assert r.status_code == 200
    assert {o["value"] for o in r.json()} >= {"", "fake", "kimi-k3"}


@pytest_db
def test_set_and_read_back_the_workspace_assistant_model() -> None:
    try:
        r = client.patch("/workspaces/current", json={"assistant_model": "kimi-k3"})
        assert r.status_code == 200
        assert r.json()["assistant_model"] == "kimi-k3"
        assert client.get("/workspaces/current").json()["assistant_model"] == "kimi-k3"
        # …and that's what /assist would resolve for this workspace.
        assert workspace_assistant_model(uuid.UUID(DEV_WORKSPACE_ID)) == "kimi-k3"
    finally:
        client.patch("/workspaces/current", json={"assistant_model": ""})


@pytest_db
def test_rejects_a_model_outside_the_allow_list() -> None:
    r = client.patch("/workspaces/current", json={"assistant_model": "o1-pro"})
    assert r.status_code == 422


@pytest_db
def test_patch_is_partial_so_a_rename_leaves_the_model_alone() -> None:
    """Regression guard: the endpoint used to take a required `name`. Saving one field must
    not silently reset the other."""
    try:
        client.patch("/workspaces/current", json={"assistant_model": "gpt-4o-mini"})
        r = client.patch("/workspaces/current", json={"name": "Renamed WS"})
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed WS"
        assert r.json()["assistant_model"] == "gpt-4o-mini"
    finally:
        client.patch("/workspaces/current", json={"name": "Dev Workspace", "assistant_model": ""})


def test_unknown_stored_model_falls_back_to_the_server_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a model is dropped from the allow-list later, affected workspaces must quietly
    revert rather than have their assistant break."""
    import calypr_api.workspace_settings as ws_settings

    monkeypatch.setattr(ws_settings, "is_allowed", lambda _m: False)
    assert workspace_assistant_model(uuid.UUID(DEV_WORKSPACE_ID)) == ""


def test_provider_catalog_only_marks_wired_providers_available() -> None:
    """A `coming_soon` row must not be storable: the UI disables it, and nothing in the model
    factory would read a key saved for it. Guards against a row being flipped to `available`
    before the backend can actually route to that provider."""
    from calypr_api.llm_providers import AVAILABLE_PROVIDERS, llm_providers
    from calypr_api.schemas import PROVIDER_KEY_PROVIDERS

    catalog = {p.provider: p for p in llm_providers()}
    assert set(catalog) == {"moonshot", "openai", "anthropic", "google"}
    assert AVAILABLE_PROVIDERS == {"moonshot", "openai", "anthropic"}
    # Anything we present as available must be a provider the key API accepts.
    assert AVAILABLE_PROVIDERS <= set(PROVIDER_KEY_PROVIDERS)
    # Google has no client in the model factory, so it must never be key-storable.
    assert "google" not in PROVIDER_KEY_PROVIDERS
    # Every coming-soon row explains itself.
    assert all(p.note for p in llm_providers() if p.status == "coming_soon")


def test_llm_providers_endpoint_serves_the_settings_list() -> None:
    r = client.get("/llm-providers")
    assert r.status_code == 200
    rows = {p["provider"]: p for p in r.json()}
    assert rows["moonshot"]["status"] == "available"
    assert rows["moonshot"]["model_label"] == "kimi-k3"
    assert rows["google"]["status"] == "coming_soon"


def test_a_key_for_an_unwired_provider_is_refused() -> None:
    """The disabled input is UI; this is the enforcement."""
    assert client.put("/provider-keys/google", json={"key": "sk-x"}).status_code == 404
