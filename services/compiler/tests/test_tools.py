"""Tools + ReAct: an agent binds a wired Tool node, calls it, loops once, and finishes —
and the generated code is the canonical `ToolNode` + `tools_condition` loop, ruff-clean."""

from __future__ import annotations

import subprocess

from calypr_codegen import generate_python
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import Done, TextDelta, ToolCall
from calypr_nodes import NodeContext
from calypr_runtime import run


class ReActFake:
    """Calls the search tool on the first turn, then answers — exactly one ReAct loop."""

    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, *, model, messages, system="", tools=None, **_):
        self.calls += 1
        if self.calls == 1:
            tc = ToolCall(id="c1", name="web_search", args={"query": "calypr"})
            yield tc
            yield Done(text="", tool_calls=[tc])
        else:
            text = "Calypr is a no-code agent builder."
            for i in range(0, len(text), 5):
                yield TextDelta(text=text[i : i + 5])
            yield Done(text=text, tool_calls=[])


def _react_graph() -> GraphSpec:
    return GraphSpec(
        id="react",
        name="ReAct",
        state=[
            StateChannel(key="input", type="string", reducer=Reducer.last),
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="output", type="string", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(
                id="in",
                type="input",
                config={"input_channel": "input", "target_channel": "messages"},
            ),
            NodeSpec(
                id="agent",
                type="agent",
                config={"model": "fake", "system_prompt": "Use tools when helpful."},
            ),
            NodeSpec(id="tools", type="tool", config={"provider": "demo_search"}),
            NodeSpec(
                id="out",
                type="output",
                config={"source_channel": "messages", "output_channel": "output"},
            ),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="agent"),
            EdgeSpec(id="e2", source="agent", target="tools", condition="tools"),
            EdgeSpec(id="e3", source="agent", target="out", condition="respond"),
            EdgeSpec(id="e4", source="tools", target="agent"),
        ],
        entry="in",
    )


async def test_react_loop_runs_the_tool_and_terminates():
    fake = ReActFake()
    result = await run(_react_graph(), NodeContext(model=fake), "what is calypr?")

    assert fake.calls == 2  # called the tool once, then answered — the loop ran and stopped
    assert result["output"] == "Calypr is a no-code agent builder."
    # the demo tool actually executed: its result is in the message history
    contents = [getattr(m, "content", "") for m in result["messages"]]
    assert any("demo results" in c for c in contents)


async def test_unrunnable_tool_answers_each_call_instead_of_crashing():
    # A Tool node with nothing to execute (here: an MCP node with no server configured) must
    # answer the agent's tool call with a ToolMessage, not raise — raising leaves a dangling
    # tool_call that poisons the next OpenAI turn.
    graph = _react_graph().model_copy(
        update={
            "nodes": [
                n.model_copy(update={"config": {"provider": "mcp"}}) if n.id == "tools" else n
                for n in _react_graph().nodes
            ]
        }
    )
    fake = ReActFake()
    result = await run(graph, NodeContext(model=fake), "what is calypr?")

    assert result["output"] == "Calypr is a no-code agent builder."  # the agent still answered
    contents = [getattr(m, "content", "") for m in result["messages"]]
    assert any("could not run" in c for c in contents)  # the tool explained itself, gracefully


def test_react_codegen_is_canonical_and_ruff_clean():
    code = generate_python(_react_graph())
    assert "from langgraph.prebuilt import ToolNode" in code
    assert "tools_condition" in code
    assert ".bind_tools([web_search])" in code
    assert "def web_search(query: str)" in code  # the demo tool, owned in the file

    fmt = subprocess.run(
        ["ruff", "format", "-"], input=code, capture_output=True, text=True
    )
    assert fmt.stdout == code, "ReAct codegen is not ruff-formatted"
    check = subprocess.run(
        ["ruff", "check", "--stdin-filename", "generated.py", "-"],
        input=code,
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, check.stdout


# ── Several Tool nodes on one agent ───────────────────────────────────────────────────────
# Binding has always unioned across every wired Tool node, so the model can pick freely. These
# cover the other half — that the *dispatch* reaches the node owning the tool it picked. Each
# ReAct edge is labelled `tools`, so the branch map used to collapse to whichever Tool node was
# declared last, leaving the others bound but unreachable.


class _CallsThenAnswers:
    """Calls the named tools on the first turn (all in one message), then answers."""

    def __init__(self, *names: str) -> None:
        self.names = names
        self.calls = 0
        self.tools_seen: list[list[dict]] = []

    async def stream(self, *, model, messages, system="", tools=None, **_):
        self.calls += 1
        self.tools_seen.append(tools or [])
        if self.calls == 1:
            tcs = [
                ToolCall(id=f"c{i}", name=n, args={"query": "q"})
                for i, n in enumerate(self.names)
            ]
            for tc in tcs:
                yield tc
            yield Done(text="", tool_calls=tcs)
        else:
            yield Done(text="done.", tool_calls=[])


def _two_tool_graph() -> GraphSpec:
    """The shape the AI assistant generates for "search the web AND read my Notion": one agent,
    two Tool nodes, both wired with a `tools` branch."""
    base = _react_graph()
    nodes = [n for n in base.nodes if n.id != "tools"]
    nodes.append(NodeSpec(id="search", type="tool", config={"provider": "demo_search"}))
    nodes.append(
        NodeSpec(
            id="photos", type="tool", config={"provider": "images_unsplash"}
        )  # keyless → deterministic stub, no network
    )
    return base.model_copy(
        update={
            "nodes": nodes,
            "edges": [
                EdgeSpec(id="e1", source="in", target="agent"),
                EdgeSpec(id="e2", source="agent", target="search", condition="tools"),
                EdgeSpec(id="e3", source="agent", target="out", condition="respond"),
                EdgeSpec(id="e4", source="search", target="agent"),
                EdgeSpec(id="e5", source="agent", target="photos", condition="tools"),
                EdgeSpec(id="e6", source="photos", target="agent"),
            ],
        }
    )


def _tool_messages(result) -> dict[str, str]:
    return {
        m.name: str(m.content)
        for m in result["messages"]
        if m.__class__.__name__ == "ToolMessage"
    }


async def test_agent_binds_every_wired_tool_node():
    fake = _CallsThenAnswers("web_search")
    await run(_two_tool_graph(), NodeContext(model=fake), "hi")
    assert sorted(t["name"] for t in fake.tools_seen[0]) == ["search_images", "web_search"]


async def test_call_reaches_the_tool_node_that_owns_it():
    # `search` is declared *before* `photos`, so a collapsed branch map would send this to
    # `photos` and the demo search would never run.
    fake = _CallsThenAnswers("web_search")
    msgs = _tool_messages(await run(_two_tool_graph(), NodeContext(model=fake), "hi"))
    assert "demo results" in msgs["web_search"]
    assert "search_images" not in msgs  # the sibling stayed out of it


async def test_call_reaches_the_later_declared_tool_node_too():
    fake = _CallsThenAnswers("search_images")
    msgs = _tool_messages(await run(_two_tool_graph(), NodeContext(model=fake), "hi"))
    assert "unsplash.com" in msgs["search_images"]
    assert "web_search" not in msgs


async def test_one_turn_calling_both_nodes_fans_out_and_answers_each_call_once():
    # The dangling-tool_call hazard: every id the assistant asked for must come back exactly
    # once, or the next OpenAI turn is poisoned.
    fake = _CallsThenAnswers("web_search", "search_images")
    result = await run(_two_tool_graph(), NodeContext(model=fake), "hi")
    tool_msgs = [m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"]
    assert sorted(m.tool_call_id for m in tool_msgs) == ["c0", "c1"]
    # Answered *once each and for real*: before the fix both ids came back too, but one of them
    # carried "is not a valid tool" from the node that didn't own it.
    msgs = _tool_messages(result)
    assert "demo results" in msgs["web_search"]
    assert "unsplash.com" in msgs["search_images"]
    assert result["output"] == "done."
