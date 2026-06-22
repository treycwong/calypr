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


def test_codegen_returns_ownable_python():
    graph = input_agent_output(model="gpt-4o-mini").model_dump()
    r = client.post("/codegen", json=graph)
    assert r.status_code == 200
    code = r.json()["code"]
    assert "def build_graph():" in code
    assert "init_chat_model" in code
    assert "import calypr" not in code


def test_templates_lists_the_archetypes():
    r = client.get("/templates")
    assert r.status_code == 200
    templates = r.json()
    ids = [t["id"] for t in templates]
    assert "tpl-simple-reflex" in ids
    assert "tpl-reflection" in ids
    assert "tpl-react" in ids
    assert len(templates) == 7
    # each carries a full, compilable graph
    first = templates[0]
    assert first["graph"]["entry"]
    assert first["description"]


@pytest.mark.skipif(not _db_available(), reason="Postgres not available")
def test_agent_crud_roundtrip():
    graph = input_agent_output(model="fake").model_dump()
    created = client.post("/agents", json={"name": "My Agent", "graph": graph})
    assert created.status_code == 200
    agent_id = created.json()["id"]

    assert any(a["id"] == agent_id for a in client.get("/agents").json())

    got = client.get(f"/agents/{agent_id}")
    assert got.status_code == 200
    assert got.json()["graph"]["id"] == "golden-input-agent-output"
