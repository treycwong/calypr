"""Reflexion: Responder → Tools → Revisor with a bounded revise loop. The loop runs the
configured number of revisions and terminates; the generated code carries the actors, the
revision counter, and the loop, ruff-clean."""

from __future__ import annotations

import subprocess

from calypr_codegen import generate_python
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import FakeModelClient
from calypr_nodes import NodeContext
from calypr_runtime import run


def _reflexion_graph(max_revisions: int = 2) -> GraphSpec:
    return GraphSpec(
        id="reflexion",
        name="Reflexion",
        state=[
            StateChannel(key="input", type="string", reducer=Reducer.last),
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="output", type="string", reducer=Reducer.last),
            StateChannel(key="revision_count", type="number", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(
                id="in",
                type="input",
                config={"input_channel": "input", "target_channel": "messages"},
            ),
            NodeSpec(id="responder", type="responder", config={"model": "fake"}),
            NodeSpec(id="tools", type="tool", config={"provider": "demo_search"}),
            NodeSpec(
                id="revisor",
                type="revisor",
                config={"model": "fake", "max_revisions": max_revisions},
            ),
            NodeSpec(
                id="out",
                type="output",
                config={"source_channel": "messages", "output_channel": "output"},
            ),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="responder"),
            EdgeSpec(id="e2", source="responder", target="tools"),
            EdgeSpec(id="e3", source="tools", target="revisor"),
            EdgeSpec(id="e4", source="revisor", target="tools", condition="revise"),
            EdgeSpec(id="e5", source="revisor", target="out", condition="done"),
        ],
        entry="in",
    )


async def test_reflexion_loop_runs_and_terminates():
    # The plain fake asks no tools (Tools no-ops); the loop is driven + bounded by the count.
    result = await run(
        _reflexion_graph(max_revisions=2), NodeContext(model=FakeModelClient()), "explain x"
    )
    assert result["revision_count"] == 2  # revised exactly twice, then finished (terminated)
    assert isinstance(result["output"], str)
    assert result["output"]


def _without_counter(graph: GraphSpec) -> GraphSpec:
    """Drop the revision_count channel — simulates the canvas sending a fixed state."""
    return graph.model_copy(
        update={"state": [c for c in graph.state if c.key != "revision_count"]}
    )


async def test_reflexion_terminates_even_when_state_omits_the_counter():
    # The canvas bug: a graph whose `state` lacks revision_count. The engine must derive it
    # from the Revisor (channels()), or the bounded loop runs away to the recursion limit.
    graph = _without_counter(_reflexion_graph(max_revisions=2))
    assert not any(c.key == "revision_count" for c in graph.state)

    result = await run(graph, NodeContext(model=FakeModelClient()), "explain x")
    assert result["revision_count"] == 2  # the derived counter still bounds the loop


def test_reflexion_codegen_includes_counter_when_state_omits_it():
    code = generate_python(_without_counter(_reflexion_graph(max_revisions=2)))
    assert "revision_count" in code  # the generated State carries the owned channel too


async def test_reflexion_runs_with_an_empty_context_resolving_own_models():
    # The playground path: context_for returns an empty NodeContext, so each actor resolves
    # its own provider (here "fake"). It must still run + terminate.
    result = await run(_reflexion_graph(max_revisions=2), NodeContext(), "explain x")
    assert result["revision_count"] == 2
    assert result["output"]


def test_reflexion_codegen_has_actors_loop_and_is_clean():
    code = generate_python(_reflexion_graph(max_revisions=2))
    assert "def node_responder(state: State)" in code
    assert "def node_revisor(state: State)" in code
    assert "def route_node_revisor(state: State)" in code
    assert "revision_count" in code
    assert "ToolNode" in code
    assert ".bind_tools([web_search])" in code

    fmt = subprocess.run(
        ["ruff", "format", "-"], input=code, capture_output=True, text=True
    )
    assert fmt.stdout == code, "Reflexion codegen is not ruff-formatted"
    check = subprocess.run(
        ["ruff", "check", "--stdin-filename", "generated.py", "-"],
        input=code,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout
