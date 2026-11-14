"""An MCP tool result is capped before it reaches the model (CAL-15).

A remote server decides how much it returns. Uncapped, DeepWiki's `read_wiki_contents` handed
back ~155k tokens and the next model call failed with a context-length 400 — reported to the user
as "check its settings". These run with no server: a fake tool is seeded into the discovery cache,
so the compiled Tool node is exercised exactly as it is in a real run.
"""

from __future__ import annotations

import pytest
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import Done, TextDelta, ToolCall
from calypr_nodes import NodeContext
from calypr_nodes.tool import MAX_MCP_RESULT_CHARS, cap_tool_content
from calypr_nodes.tools_catalog import _MCP_CACHE
from calypr_runtime import run
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool

URL = "http://mcp.test/mcp"


def test_short_content_is_untouched():
    assert cap_tool_content("hello") == "hello"
    blocks = [{"type": "text", "text": "a"}, {"type": "image", "data": "x"}]
    assert cap_tool_content(blocks) is blocks


def test_long_string_is_cut_and_says_so():
    out = cap_tool_content("x" * 50, limit=10)
    assert out.startswith("x" * 10)
    assert "x" * 11 not in out
    assert "Result truncated: showing the first 10 of 50 characters" in out


def test_text_blocks_share_one_budget_and_other_blocks_survive():
    image = {"type": "image", "data": "abc"}
    blocks = [
        {"type": "text", "text": "a" * 6},
        image,
        {"type": "text", "text": "b" * 6},
        {"type": "text", "text": "c" * 6},
    ]
    out = cap_tool_content(blocks, limit=10)
    texts = [b["text"] for b in out if b.get("type") == "text"]
    assert texts[0] == "a" * 6
    assert texts[1] == "b" * 4  # the remaining budget
    assert all("c" not in t for t in texts[:-1])  # past the budget: dropped
    assert "showing the first 10 of 18 characters" in texts[-1]
    assert image in out


@pytest.fixture
def huge_mcp_tool():
    def read_wiki_contents(repo: str) -> list[dict]:
        """Return a whole wiki."""
        return [{"type": "text", "text": "w" * (MAX_MCP_RESULT_CHARS * 10)}]

    tool = StructuredTool.from_function(read_wiki_contents, response_format="content")
    _MCP_CACHE[(URL, "streamable_http", ())] = [tool]
    yield tool
    _MCP_CACHE.clear()


class _WikiReaderFake:
    """Asks for the whole wiki once, then answers, recording what the model was sent."""

    def __init__(self) -> None:
        self.calls = 0
        self.seen: list = []

    async def stream(self, *, model, messages, system="", tools=None, **_):
        self.calls += 1
        self.seen = list(messages)
        if self.calls == 1:
            tc = ToolCall(id="c1", name="read_wiki_contents", args={"repo": "a/b"})
            yield tc
            yield Done(text="", tool_calls=[tc])
        else:
            yield TextDelta(text="Done.")
            yield Done(text="Done.", tool_calls=[])


def _graph() -> GraphSpec:
    return GraphSpec(
        id="mcp-cap",
        name="MCP cap",
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
            NodeSpec(id="agent", type="agent", config={"model": "fake"}),
            NodeSpec(id="tools", type="tool", config={"provider": "mcp", "mcp_url": URL}),
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


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)


async def test_an_oversized_mcp_result_reaches_the_model_capped(huge_mcp_tool):
    fake = _WikiReaderFake()
    result = await run(_graph(), NodeContext(model=fake), "read the wiki")

    [tool_msg] = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    text = _text(tool_msg.content)
    # The tool returned 200k characters; the transcript keeps the budget plus a short note.
    assert len(text) < MAX_MCP_RESULT_CHARS + 300
    assert "Result truncated" in text
    # ...and that capped result is what the model was actually sent on its second turn.
    # (The client sees its own message shape, so check every message's size, whatever it is.)
    assert fake.calls == 2 and fake.seen
    assert max(len(str(m)) for m in fake.seen) < MAX_MCP_RESULT_CHARS + 2_000
    assert result["output"] == "Done."
