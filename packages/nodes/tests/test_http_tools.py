"""HTTP tool providers — API access as a *tool* the agent decides to call (Phase 8a).

`images_unsplash` and `generic_http` ride the existing Tool node: same ToolNode contract, same
ReAct loop, same edge-driven binding as `demo_search`. Two invariants get the most attention
here because they're what makes the providers safe to ship:

- **keyless is green** — without an Unsplash key the tool returns deterministic stub photos, so
  the canvas, CI, and E2E run with zero setup (the `demo_search` trick);
- **failures never raise** — a raised exception would leave the assistant's `tool_calls`
  unanswered and corrupt the thread on the next turn, so every error path returns a sentence.
"""

from __future__ import annotations

import os

import httpx
import pytest
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import Done, TextDelta, ToolCall
from calypr_nodes import NodeContext
from calypr_nodes.tool import ToolConfig, ToolsNode
from calypr_nodes.tools_catalog import tool_spec
from calypr_runtime import run

_PHOTOS = {
    "results": [
        {
            "description": "a foggy forest",
            "alt_description": None,
            "urls": {"regular": "https://images.unsplash.com/photo-1"},
            "user": {"name": "Ada Lovelace"},
        }
    ]
}


def _invoke(spec, **kwargs) -> str:
    return spec.runtime.invoke(kwargs)


# ── Unsplash ──────────────────────────────────────────────────────────────────────────────


def test_unsplash_without_key_returns_deterministic_stub():
    spec = tool_spec("images_unsplash")
    out = _invoke(spec, query="foggy forest")
    assert out == _invoke(spec, query="anything else")  # deterministic, query-independent
    assert "unsplash.com" in out
    # Reads as a *successful* search with placeholder results, never as a failure — an earlier
    # wording made the model apologise and show nothing, breaking the keyless first run.
    assert out.startswith("Search succeeded.")
    assert "Settings → API Keys" in out


def test_unsplash_with_key_formats_photos(monkeypatch):
    def fake_get(url, **kwargs):
        assert url.endswith("/search/photos")
        assert kwargs["params"] == {"query": "foggy forest", "per_page": 2}
        assert kwargs["headers"]["Authorization"] == "Client-ID k-123"
        return httpx.Response(200, json=_PHOTOS, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    out = _invoke(
        tool_spec("images_unsplash", api_key="k-123", max_results=2), query="foggy forest"
    )
    # Agent-shaped: one line per photo, not raw JSON.
    assert out == "a foggy forest — https://images.unsplash.com/photo-1 (by Ada Lovelace)"


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "rejected the API key"), (403, "Rate-limited"), (500, "HTTP 500")],
)
def test_unsplash_errors_are_explained_not_raised(monkeypatch, status: int, expected: str):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **kw: httpx.Response(status, request=httpx.Request("GET", url)),
    )
    out = _invoke(tool_spec("images_unsplash", api_key="k"), query="x")
    assert expected in out


def test_unsplash_network_failure_is_explained_not_raised(monkeypatch):
    def boom(url, **kwargs):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "get", boom)
    assert "network error" in _invoke(tool_spec("images_unsplash", api_key="k"), query="x")


# ── Tavily ────────────────────────────────────────────────────────────────────────────────
# Note the deliberate asymmetry with Unsplash: a keyless Tavily says so plainly instead of
# serving stub results. Placeholder photos are harmless; placeholder *search results* would be
# fabricated facts the agent relays as real.

_RESULTS = {
    "results": [
        {
            "title": "Gordon Ryan wins again",
            "url": "https://example.test/adcc",
            "content": "He submitted the field.",
        }
    ]
}


def test_tavily_without_key_refuses_instead_of_inventing_results():
    out = _invoke(tool_spec("tavily"), query="latest bjj news")
    assert "no Tavily API key" in out
    assert "Settings → API Keys" in out
    assert "Do not invent results." in out


def test_tavily_with_key_posts_and_formats_results(monkeypatch):
    def fake_post(url, **kwargs):
        assert url == "https://api.tavily.com/search"
        assert kwargs["json"] == {"query": "latest bjj news", "max_results": 2}
        assert kwargs["headers"]["Authorization"] == "Bearer tvly-123"
        return httpx.Response(200, json=_RESULTS, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", fake_post)
    out = _invoke(tool_spec("tavily", api_key="tvly-123", max_results=2), query="latest bjj news")
    assert out == "Gordon Ryan wins again — https://example.test/adcc\nHe submitted the field."


def test_tavily_key_is_never_baked_into_the_bind_schema():
    # The schema goes to the model provider verbatim — a key leaking in would ship to OpenAI.
    spec = tool_spec("tavily", api_key="tvly-secret")
    assert spec.bind_schema["name"] == "web_search"  # same name as demo_search: swapping the
    assert "tvly-secret" not in str(spec.bind_schema)  # provider must not rename the tool


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "rejected the API key"),
        (429, "Rate-limited"),
        (432, "plan limit"),
        (500, "HTTP 500"),
    ],
)
def test_tavily_errors_are_explained_not_raised(monkeypatch, status: int, expected: str):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: httpx.Response(status, request=httpx.Request("POST", url)),
    )
    assert expected in _invoke(tool_spec("tavily", api_key="k"), query="x")


def test_tavily_network_failure_is_explained_not_raised(monkeypatch):
    def boom(url, **kwargs):
        raise httpx.ConnectError("no route")

    monkeypatch.setattr(httpx, "post", boom)
    assert "network error" in _invoke(tool_spec("tavily", api_key="k"), query="x")


def test_tavily_empty_results_do_not_look_like_a_failure(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "post",
        lambda url, **kw: httpx.Response(
            200, json={"results": []}, request=httpx.Request("POST", url)
        ),
    )
    out = _invoke(tool_spec("tavily", api_key="k"), query="x")
    assert out == "No web results matched that search."


# ── generic_http ──────────────────────────────────────────────────────────────────────────


def test_generic_http_substitutes_query_and_digs_the_path(monkeypatch):
    def fake_get(url, **kwargs):
        assert url == "https://api.example.com/search"
        assert kwargs["params"] == {"q": "lisbon", "limit": "5"}
        return httpx.Response(
            200, json={"results": [{"name": "Lisbon"}]}, request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    spec = tool_spec(
        "generic_http",
        http_url="https://api.example.com/search",
        http_params={"q": "{query}", "limit": "5"},
        jsonpath="results.0.name",
    )
    assert _invoke(spec, query="lisbon") == '"Lisbon"'


def test_generic_http_missing_path_is_explained(monkeypatch):
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, **kw: httpx.Response(200, json={}, request=httpx.Request("GET", url)),
    )
    spec = tool_spec("generic_http", http_url="https://x.test", jsonpath="a.b")
    assert "nothing at 'a.b'" in _invoke(spec, query="q")


def test_generic_http_without_url_is_explained():
    assert "No URL is configured" in _invoke(tool_spec("generic_http"), query="q")


# ── codegen ───────────────────────────────────────────────────────────────────────────────


def test_codegen_reads_the_key_from_env_never_inline():
    cfg = ToolConfig(provider="images_unsplash", api_key="super-secret", max_results=4)
    code = ToolsNode.codegen(cfg, "node_tools").function
    assert "super-secret" not in code
    assert "os.environ['UNSPLASH_ACCESS_KEY']" in code
    assert "_UNSPLASH_RESULTS = 4" in code
    assert "node_tools = ToolNode([search_images])" in code


def test_codegen_http_emits_the_configured_request():
    cfg = ToolConfig(
        provider="generic_http",
        http_url="https://api.example.com/s",
        http_params={"q": "{query}"},
        jsonpath="results.0",
    )
    code = ToolsNode.codegen(cfg, "node_tools").function
    assert "_HTTP_URL = 'https://api.example.com/s'" in code
    assert "_HTTP_PARAMS = {'q': '{query}'}" in code
    assert "node_tools = ToolNode([fetch])" in code


# ── the ReAct loop (the shipped template's shape) ─────────────────────────────────────────


class _SearchThenAnswerFake:
    """Calls `search_images` on the first turn, then answers — exactly one ReAct loop."""

    def __init__(self) -> None:
        self.calls = 0
        self.tools_seen: list = []

    async def stream(self, *, model, messages, system="", tools=None, **_):
        self.calls += 1
        self.tools_seen.append(tools)
        if self.calls == 1:
            tc = ToolCall(id="c1", name="search_images", args={"query": "foggy forest"})
            yield tc
            yield Done(text="", tool_calls=[tc])
        else:
            text = "Here's the best match."
            yield TextDelta(text=text)
            yield Done(text=text, tool_calls=[])


def _image_finder_graph() -> GraphSpec:
    return GraphSpec(
        id="image-finder",
        name="Image Finder",
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
            NodeSpec(id="tools", type="tool", config={"provider": "images_unsplash"}),
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


async def test_agent_searches_images_through_the_react_loop():
    """Keyless end-to-end: the agent binds `search_images`, calls it, and the stub photos come
    back as a ToolMessage — the canvas path with no key and no network."""
    fake = _SearchThenAnswerFake()
    result = await run(_image_finder_graph(), NodeContext(model=fake), "find me a forest photo")

    bound = [t["name"] for t in (fake.tools_seen[0] or [])]
    assert bound == ["search_images"]  # edge-driven binding, unchanged from demo_search
    tool_msgs = [m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"]
    assert tool_msgs, "expected a search_images ToolMessage in the transcript"
    assert "unsplash.com" in str(tool_msgs[0].content)
    assert result["output"] == "Here's the best match."


@pytest.mark.skipif(
    not os.environ.get("TAVILY_API_KEY"), reason="no TAVILY_API_KEY — offline dev"
)
def test_live_tavily_search():
    out = _invoke(
        tool_spec("tavily", api_key=os.environ["TAVILY_API_KEY"], max_results=2),
        query="latest brazilian jiu-jitsu news",
    )
    assert "http" in out  # real result lines carry URLs
    assert "unavailable" not in out


@pytest.mark.skipif(
    not os.environ.get("UNSPLASH_ACCESS_KEY"), reason="no UNSPLASH_ACCESS_KEY — offline dev"
)
def test_live_unsplash_search():
    out = _invoke(
        tool_spec("images_unsplash", api_key=os.environ["UNSPLASH_ACCESS_KEY"], max_results=2),
        query="foggy forest",
    )
    assert "images.unsplash.com" in out
