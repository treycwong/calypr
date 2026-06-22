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
