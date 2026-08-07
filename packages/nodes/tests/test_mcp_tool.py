"""MCP provider on the Tool node — discovers a real MCP server's tools over HTTP and runs
them through the same ToolNode contract as demo_search. The test target is the official
`@modelcontextprotocol/server-everything` reference server (spun up over Streamable HTTP);
the test skips cleanly when Node/npx or the server are unavailable so offline dev stays green.

The MCP-specific wiring — many tools from one server, async discovery from a sync compile —
lives entirely in `tools_catalog.py`; every other node is unchanged."""

from __future__ import annotations

import shutil
import socket
import subprocess
import time
import urllib.request

import pytest
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import Done, TextDelta, ToolCall
from calypr_nodes import NodeContext
from calypr_nodes.tool import ToolConfig, ToolsNode
from calypr_nodes.tools_catalog import _MCP_CACHE
from calypr_runtime import run


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve():
    """Start `server-everything` over Streamable HTTP; yield its /mcp URL. Skip if unavailable."""
    if shutil.which("npx") is None:
        pytest.skip("npx not available — skipping live MCP server test")
    port = _free_port()
    proc = subprocess.Popen(
        ["npx", "-y", "@modelcontextprotocol/server-everything", "streamableHttp"],
        env={"PORT": str(port), "PATH": __import__("os").environ.get("PATH", "")},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/mcp"
    try:
        for _ in range(60):  # up to ~30s: first run downloads the package
            if proc.poll() is not None:
                pytest.skip("server-everything exited before becoming ready")
            try:
                urllib.request.urlopen(url, timeout=1)  # noqa: S310 — localhost test server
            except urllib.error.HTTPError:
                break  # any HTTP response means the server is up (400 without a session)
            except OSError:
                time.sleep(0.5)
        else:
            pytest.skip("server-everything did not become ready in time")
        _MCP_CACHE.clear()
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        _MCP_CACHE.clear()


@pytest.fixture(scope="module")
def mcp_server():
    yield from _serve()


@pytest.fixture(scope="module")
def mcp_server_b():
    """A *second* live server, so the multi-server tests exercise two real connections rather
    than one URL used twice (which the discovery cache would collapse into a single client)."""
    yield from _serve()


def test_bind_schemas_returns_many_tools(mcp_server: str):
    cfg = ToolConfig(provider="mcp", mcp_url=mcp_server)
    schemas = ToolsNode.bind_schemas(cfg)
    assert len(schemas) > 1  # one server yields N tools (the plural-schema path)
    names = {s["name"] for s in schemas}
    assert "echo" in names
    assert all("input_schema" in s for s in schemas)


def test_tool_filter_selects_subset(mcp_server: str):
    cfg = ToolConfig(provider="mcp", mcp_url=mcp_server, mcp_tool_filter=["echo"])
    schemas = ToolsNode.bind_schemas(cfg)
    assert [s["name"] for s in schemas] == ["echo"]


class _EchoReActFake:
    """Calls the MCP `echo` tool on the first turn, then answers — exactly one ReAct loop."""

    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, *, model, messages, system="", tools=None, **_):
        self.calls += 1
        if self.calls == 1:
            tc = ToolCall(id="c1", name="echo", args={"message": "hi mcp"})
            yield tc
            yield Done(text="", tool_calls=[tc])
        else:
            text = "Done."
            yield TextDelta(text=text)
            yield Done(text=text, tool_calls=[])


def _mcp_react_graph(url: str) -> GraphSpec:
    return GraphSpec(
        id="mcp-react",
        name="MCP ReAct",
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
            NodeSpec(
                id="tools",
                type="tool",
                config={"provider": "mcp", "mcp_url": url, "mcp_tool_filter": ["echo"]},
            ),
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


async def test_agent_calls_mcp_tool_through_react_loop(mcp_server: str):
    """End-to-end: an Agent binds the MCP server's tools, calls `echo`, and the ToolMessage
    flows back through the canonical ReAct loop — MCP composing with other nodes unchanged."""
    ctx = NodeContext(model=_EchoReActFake())
    result = await run(_mcp_react_graph(mcp_server), ctx, "please echo")
    messages = result["messages"]
    tool_msgs = [m for m in messages if m.__class__.__name__ == "ToolMessage"]
    assert tool_msgs, "expected an MCP ToolMessage in the transcript"
    assert any("hi mcp" in str(m.content) for m in tool_msgs)
    assert result["output"] == "Done."


class _TwoServerFake:
    """Calls one tool from each of two MCP servers in a single turn, then answers.

    This is the case a single `tools` branch cannot serve: the router has to fan out to both
    Tool nodes, and each must answer only its own call."""

    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, *, model, messages, system="", tools=None, **_):
        self.calls += 1
        if self.calls == 1:
            a = ToolCall(id="c1", name="echo", args={"message": "from a"})
            b = ToolCall(id="c2", name="get-sum", args={"a": 2, "b": 3})
            yield a
            yield b
            yield Done(text="", tool_calls=[a, b])
        else:
            text = "Both done."
            yield TextDelta(text=text)
            yield Done(text=text, tool_calls=[])


def _two_server_graph(url_a: str, url_b: str) -> GraphSpec:
    """One agent, two MCP Tool nodes — the shape of the GitHub + Notion template. Each node is
    filtered to a single tool so ownership is unambiguous even though both servers are the same
    reference implementation."""
    g = _mcp_react_graph(url_a)
    nodes = [
        *g.nodes,
        NodeSpec(
            id="tools_b",
            type="tool",
            config={"provider": "mcp", "mcp_url": url_b, "mcp_tool_filter": ["get-sum"]},
        ),
    ]
    edges = [
        *g.edges,
        EdgeSpec(id="e5", source="agent", target="tools_b", condition="tools"),
        EdgeSpec(id="e6", source="tools_b", target="agent"),
    ]
    return g.model_copy(update={"nodes": nodes, "edges": edges})


async def test_two_mcp_servers_each_answer_their_own_calls(mcp_server: str, mcp_server_b: str):
    """Two Tool nodes, two live servers, both called in one turn.

    Guards the invariant that makes multi-server MCP work at all: every tool call is answered
    exactly once, by the node that owns it. A regression here shows up as a duplicated or
    missing `tool_call_id`, which corrupts the thread on the next turn."""
    ctx = NodeContext(model=_TwoServerFake())
    result = await run(_two_server_graph(mcp_server, mcp_server_b), ctx, "use both")
    tool_msgs = [m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"]
    ids = [m.tool_call_id for m in tool_msgs]
    assert sorted(ids) == ["c1", "c2"], f"each call answered exactly once, got {ids}"
    by_id = {m.tool_call_id: str(m.content) for m in tool_msgs}
    assert "from a" in by_id["c1"]  # the echo server answered the echo call
    assert "5" in by_id["c2"]  # the second server answered the sum call
    assert result["output"] == "Both done."


def test_tool_nodes_do_not_share_a_server(mcp_server: str, mcp_server_b: str):
    """Each node binds only its own server's (filtered) tools — no leakage between siblings."""
    a = ToolsNode.bind_schemas(
        ToolConfig(provider="mcp", mcp_url=mcp_server, mcp_tool_filter=["echo"])
    )
    b = ToolsNode.bind_schemas(
        ToolConfig(provider="mcp", mcp_url=mcp_server_b, mcp_tool_filter=["get-sum"])
    )
    assert [s["name"] for s in a] == ["echo"]
    assert [s["name"] for s in b] == ["get-sum"]
