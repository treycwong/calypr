"""The workspace default model: what an LLM node runs on when it doesn't name one.

Node configs ship `model: ""`, so this setting decides the whole canvas. The rules that matter:
an explicit per-node choice always wins, an unset workspace still gets a *working* model (never
`fake`), and the generated code names whatever the run would actually use.
"""

from __future__ import annotations

import pytest
from calypr_api.db.models import Workspace
from calypr_api.db.session import SessionLocal, engine
from calypr_api.main import app
from calypr_api.workspace_model import apply_default_model, strip_fake_models
from calypr_compiler.golden import input_agent_output
from calypr_nodes import NodeContext
from calypr_nodes.registry import PLATFORM_DEFAULT_MODEL, effective_model
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


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


# --- resolution order -------------------------------------------------------------------------


def test_a_node_that_names_a_model_keeps_it():
    ctx = NodeContext(default_model="claude-sonnet-4-5")
    assert effective_model(ctx, "gpt-4o") == "gpt-4o"


def test_an_inheriting_node_takes_the_workspace_default():
    ctx = NodeContext(default_model="claude-sonnet-4-5")
    assert effective_model(ctx, "") == "claude-sonnet-4-5"


def test_with_no_preference_anywhere_it_lands_on_the_platform_default():
    assert effective_model(NodeContext(), "") == PLATFORM_DEFAULT_MODEL


def test_the_platform_default_is_a_real_model():
    # The whole point of the pivot fix: `fake` answers "Echo: …", which must never be what a
    # user gets for not having chosen anything.
    assert PLATFORM_DEFAULT_MODEL != "fake"


# --- applying it to a graph (the codegen path) -------------------------------------------------


def test_apply_fills_in_only_the_inheriting_nodes():
    graph = input_agent_output()
    graph.nodes[1].config["model"] = ""
    patched = apply_default_model(graph, "claude-sonnet-4-5")
    assert patched.nodes[1].config["model"] == "claude-sonnet-4-5"


def test_apply_never_overrides_an_explicit_choice():
    graph = input_agent_output(model="gpt-4o")
    patched = apply_default_model(graph, "claude-sonnet-4-5")
    assert patched.nodes[1].config["model"] == "gpt-4o"


def test_apply_leaves_the_graph_alone_with_no_preference():
    graph = input_agent_output(model="")
    assert apply_default_model(graph, "") is graph


def test_apply_does_not_mutate_the_caller_s_graph():
    # The run path hands the request's own spec around; patching it in place would leak the
    # workspace's preference into whatever the caller does next with that object.
    graph = input_agent_output(model="")
    apply_default_model(graph, "claude-sonnet-4-5")
    assert graph.nodes[1].config["model"] == ""


# --- the setting itself ------------------------------------------------------------------------


@requires_db
def test_workspace_reports_and_accepts_a_default_model():
    original = client.get("/workspaces/current").json()["default_model"]
    try:
        r = client.patch("/workspaces/current", json={"default_model": "gpt-4o"})
        assert r.status_code == 200
        assert r.json()["default_model"] == "gpt-4o"
        assert client.get("/workspaces/current").json()["default_model"] == "gpt-4o"
    finally:
        client.patch("/workspaces/current", json={"default_model": original})


@requires_db
def test_an_unsupported_model_is_refused():
    # Allow-listed, because this value reaches the model factory for every inheriting node.
    assert client.patch("/workspaces/current", json={"default_model": "gpt-9"}).status_code == 422


@requires_db
def test_codegen_emits_the_workspace_default_not_the_platform_one():
    """Generated code must name what a run would use, or the file you download quietly
    disagrees with the product that produced it."""
    original = client.get("/workspaces/current").json()["default_model"]
    try:
        client.patch("/workspaces/current", json={"default_model": "gpt-4o"})
        graph = input_agent_output(model="").model_dump(mode="json")
        code = client.post("/codegen", json=graph).json()["code"]
        assert '"gpt-4o"' in code
        assert PLATFORM_DEFAULT_MODEL not in code
    finally:
        client.patch("/workspaces/current", json={"default_model": original})


@requires_db
def test_codegen_falls_back_to_the_platform_default_when_unset():
    original = client.get("/workspaces/current").json()["default_model"]
    try:
        client.patch("/workspaces/current", json={"default_model": ""})
        graph = input_agent_output(model="").model_dump(mode="json")
        code = client.post("/codegen", json=graph).json()["code"]
        assert f'"{PLATFORM_DEFAULT_MODEL}"' in code, "generated code must name a real model"
    finally:
        client.patch("/workspaces/current", json={"default_model": original})


@requires_db
def test_the_dev_workspace_ships_inheriting():
    with SessionLocal() as s:
        for ws in s.query(Workspace).all():
            assert ws.default_model in ("", "gpt-4o", "gpt-4o-mini", "claude-sonnet-4-5"), (
                "a workspace should not be left on some ad-hoc model id"
            )


# --- repairing agents that were saved with `fake` (migration 0011) -----------------------------


def test_strip_rewrites_fake_on_llm_nodes():
    spec = {
        "nodes": [
            {"id": "responder", "type": "responder", "config": {"model": "fake"}},
            {"id": "revisor", "type": "revisor", "config": {"model": "fake"}},
        ]
    }
    patched, changed = strip_fake_models(spec)
    assert changed == 2
    assert [n["config"]["model"] for n in patched["nodes"]] == ["", ""]


def test_strip_leaves_a_deliberate_real_model_alone():
    spec = {"nodes": [{"id": "a", "type": "agent", "config": {"model": "gpt-4o"}}]}
    _, changed = strip_fake_models(spec)
    assert changed == 0


def test_strip_ignores_media_nodes():
    # `fake` means something different on these (a keyless *image*/*speech* stub) and they
    # resolve through their own factories, so the workspace default must not touch them.
    spec = {
        "nodes": [
            {"id": "img", "type": "image", "config": {"model": "fake"}},
            {"id": "tts", "type": "tts", "config": {"model": "fake"}},
        ]
    }
    _, changed = strip_fake_models(spec)
    assert changed == 0


@pytest.mark.parametrize("junk", [{}, {"nodes": None}, {"nodes": ["not-a-dict"]}, {"nodes": [{}]}])
def test_strip_tolerates_rows_written_by_older_code(junk):
    # A migration reads whatever is in the column, including shapes today's GraphSpec would
    # refuse. It must not raise mid-upgrade.
    _, changed = strip_fake_models(junk)
    assert changed == 0
