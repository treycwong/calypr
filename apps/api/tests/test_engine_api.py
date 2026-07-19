import pytest
from calypr_api.db.session import engine
from calypr_api.main import app
from calypr_compiler.golden import input_agent_output
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


def test_compile_accepts_valid_graph():
    graph = input_agent_output(model="fake").model_dump()
    r = client.post("/compile", json=graph)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_compile_reports_errors_for_bad_graph():
    bad = {
        "schema_version": "0.1.0",
        "id": "bad",
        "name": "bad",
        "state": [{"key": "messages", "type": "messages", "reducer": "append"}],
        "nodes": [{"id": "in", "type": "input", "config": {}}],
        "edges": [],
        "entry": "in",
    }
    r = client.post("/compile", json=bad)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "no_output" in {i["code"] for i in body["issues"]}


def test_run_streams_tokens_with_fake_model():
    graph = input_agent_output(model="fake").model_dump()
    r = client.post("/runs", json={"graph": graph, "message": "hello world"})
    assert r.status_code == 200
    body = r.text
    assert "Echo:" in body
    assert '"type": "final"' in body


def test_runs_stays_public_when_internal_key_is_set(monkeypatch):
    """Regression: with an internal key set (prod), an unauthenticated /runs call must still
    stream — the playground proxy is not tenant-scoped, so run_workspace falls back to the dev
    workspace instead of 401-ing. (PR-2 briefly broke this by requiring request_workspace.)"""
    from calypr_api.config import settings

    monkeypatch.setattr(settings, "internal_key", "prod-key")
    graph = input_agent_output(model="fake").model_dump()
    r = client.post("/runs", json={"graph": graph, "message": "hello world"})
    assert r.status_code == 200
    assert "Echo:" in r.text
    assert '"type": "error"' not in r.text


def test_codegen_returns_ownable_python():
    graph = input_agent_output(model="gpt-4o-mini").model_dump()
    r = client.post("/codegen", json=graph)
    assert r.status_code == 200
    code = r.json()["code"]
    assert "def build_graph():" in code
    assert "init_chat_model" in code
    assert "import calypr" not in code


def test_templates_lists_frameworks_and_use_case_templates():
    r = client.get("/templates")
    assert r.status_code == 200
    starters = r.json()
    by_kind = {s["id"]: s["kind"] for s in starters}
    # frameworks (agent patterns) + templates (use cases), each tagged with its kind
    assert by_kind["tpl-react"] == "framework"
    assert by_kind["tpl-reflexion"] == "framework"
    assert by_kind["tpl-market-research"] == "template"
    assert by_kind["tpl-contract-review"] == "template"
    assert by_kind["tpl-rag"] == "framework"
    assert by_kind["tpl-routing"] == "template"
    assert by_kind["tpl-trip-planner"] == "template"
    assert by_kind["tpl-image-generation"] == "template"
    assert by_kind["tpl-text-to-speech"] == "template"
    assert by_kind["tpl-translate-speak"] == "template"
    assert by_kind["tpl-label-reader"] == "template"
    assert by_kind["tpl-alt-text"] == "template"
    assert by_kind["tpl-mcp-react"] == "framework"
    assert len(starters) == 20  # 10 frameworks + 10 templates
    # each carries a full, compilable graph
    first = starters[0]
    assert first["graph"]["entry"]
    assert first["description"]


@pytest.mark.skipif(not _db_available(), reason="Postgres not available")
def test_agent_crud_roundtrip():
    graph = input_agent_output(model="fake").model_dump()
    created = client.post("/agents", json={"name": "My Agent", "graph": graph})
    assert created.status_code == 200
    agent_id = created.json()["id"]

    summaries = client.get("/agents").json()
    mine = next(a for a in summaries if a["id"] == agent_id)
    assert "updated_at" in mine  # the dashboard sorts/labels by this

    got = client.get(f"/agents/{agent_id}")
    assert got.status_code == 200
    assert got.json()["graph"]["id"] == "golden-input-agent-output"

    # delete → gone from the list + 404 on fetch
    assert client.delete(f"/agents/{agent_id}").status_code == 204
    assert all(a["id"] != agent_id for a in client.get("/agents").json())
    assert client.get(f"/agents/{agent_id}").status_code == 404


@pytest.mark.skipif(not _db_available(), reason="Postgres not available")
def test_per_user_workspace_isolation(monkeypatch):
    """With the internal key set, two users resolve to separate workspaces and can't see each
    other's agents; a request without the key is rejected."""
    from calypr_api.config import settings

    monkeypatch.setattr(settings, "internal_key", "test-key")
    graph = input_agent_output(model="fake").model_dump()

    def hdr(uid: str) -> dict[str, str]:
        return {"x-calypr-internal-key": "test-key", "x-calypr-user-id": uid}

    a = client.post("/agents", json={"name": "A", "graph": graph}, headers=hdr("user-a"))
    assert a.status_code == 200
    a_id = a.json()["id"]

    assert any(x["id"] == a_id for x in client.get("/agents", headers=hdr("user-a")).json())
    assert all(x["id"] != a_id for x in client.get("/agents", headers=hdr("user-b")).json())

    # missing/incorrect internal key → 401 (can't spoof identity from the public internet)
    assert client.get("/agents", headers={"x-calypr-user-id": "user-a"}).status_code == 401
