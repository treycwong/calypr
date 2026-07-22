"""Tool catalog — the providers a Tool node can execute or generate (Phase 5).

Each provider yields everything the rest of the engine needs: a LangChain `BaseTool` to
execute (or None for codegen-only providers), a unified bind-schema so an LLM node can
`model.bind_tools(...)`/`stream(tools=...)`, and the Python (defs + a reference + imports)
to emit in the owned, standalone module. `demo_search` runs with no key or network so the
canvas, tests, and keyless playground stay deterministic; `tavily` is codegen-only for now."""

from __future__ import annotations

import asyncio
import json
import threading
from dataclasses import dataclass, field

import httpx
from langchain_core.tools import BaseTool, tool
from langchain_core.utils.function_calling import convert_to_openai_function


@tool
def web_search(query: str) -> str:
    """Search the web for `query` and return a short result snippet."""
    return f"[demo results for {query!r}]"


_DEMO_DEF = '''@tool
def web_search(query: str) -> str:
    """Search the web for `query` and return a short result snippet."""
    return f"[demo results for {query!r}]"'''


# ── HTTP providers ────────────────────────────────────────────────────────────────────────
# API access as a *tool*: the agent decides when to call and judges the results (the ReAct
# shape), rather than a node fetching deterministically. Both providers execute on the canvas.
#
# Two rules hold for every HTTP tool here:
#   1. **Never raise.** A raised exception leaves the assistant's `tool_calls` unanswered and
#      corrupts the thread for the next turn (same reasoning as `tool.py`'s codegen-only note).
#      Failures come back as a sentence the agent can relay.
#   2. **Never inline a key.** The runtime takes it as an argument (vault-injected server-side);
#      the generated code reads `os.environ`.

_MAX_TOOL_CHARS = 4000  # keep a single tool result from swamping the context window

UNSPLASH_SEARCH_URL = "https://api.unsplash.com/search/photos"


def _truncate(text: str) -> str:
    return text[:_MAX_TOOL_CHARS]


def _format_unsplash(payload: dict) -> str:
    """Agent-shaped photo lines, not 4 KB of JSON — description, URL, photographer."""
    results = payload.get("results") or []
    if not results:
        return "No photos matched that search."
    lines = []
    for photo in results:
        desc = photo.get("description") or photo.get("alt_description") or "untitled"
        url = (photo.get("urls") or {}).get("regular", "")
        who = ((photo.get("user") or {}).get("name")) or "unknown"
        lines.append(f"{desc} — {url} (by {who})")
    return _truncate("\n".join(lines))


# Phrased as a *successful* search whose results happen to be placeholders. An earlier wording
# ("no Unsplash key on file") read to the model as a failure, and it apologised and refused to
# show anything — which breaks the keyless first-run demo the stub exists to protect.
_UNSPLASH_STUB = (
    "Search succeeded. These are demo placeholder photos (Calypr has no Unsplash key on file "
    "yet). Present them exactly as you would real results, then add one short line telling the "
    "user to add an Unsplash key in Settings → API Keys for live photos.\n"
    "a foggy pine forest at dawn — https://images.unsplash.com/demo-1 (by Demo Photographer)\n"
    "sunlight through tall trees — https://images.unsplash.com/demo-2 (by Demo Photographer)\n"
    "a quiet woodland path — https://images.unsplash.com/demo-3 (by Demo Photographer)"
)


def _unsplash_tool(api_key: str, max_results: int) -> BaseTool:
    """The Unsplash search tool. Without a key it returns deterministic stub results, so the
    canvas, CI, and E2E run with zero setup — exactly like `demo_search`."""

    @tool
    def search_images(query: str) -> str:
        """Search Unsplash for photos matching `query`. Returns one line per photo:
        description, image URL, and photographer."""
        if not api_key:
            return _UNSPLASH_STUB
        try:
            r = httpx.get(
                UNSPLASH_SEARCH_URL,
                params={"query": query, "per_page": max_results},
                headers={"Authorization": f"Client-ID {api_key}"},
                timeout=10,
            )
        except httpx.HTTPError:
            return "Could not reach Unsplash (network error) — try again in a moment."
        if r.status_code == 401:
            return "Unsplash rejected the API key — check it in Settings → API Keys."
        if r.status_code == 403:
            return "Rate-limited by Unsplash (free tier is 50 requests/hour) — try again later."
        if r.status_code >= 400:
            return f"Unsplash returned an error (HTTP {r.status_code})."
        try:
            return _format_unsplash(r.json())
        except ValueError:
            return "Unsplash returned a response that could not be read."

    return search_images


_UNSPLASH_DEFS = [
    "_UNSPLASH_RESULTS = {max_results}",
    '''@tool
def search_images(query: str) -> str:
    """Search Unsplash for photos matching `query`. Returns one line per photo:
    description, image URL, and photographer."""
    r = httpx.get(
        "https://api.unsplash.com/search/photos",
        params={"query": query, "per_page": _UNSPLASH_RESULTS},
        headers={"Authorization": f"Client-ID {os.environ['UNSPLASH_ACCESS_KEY']}"},
        timeout=10,
    )
    r.raise_for_status()
    lines = []
    for photo in r.json().get("results", []):
        desc = photo.get("description") or photo.get("alt_description") or "untitled"
        url = photo.get("urls", {}).get("regular", "")
        who = photo.get("user", {}).get("name", "unknown")
        lines.append(f"{desc} — {url} (by {who})")
    return "\\n".join(lines)[:4000] or "No photos matched that search."''',
]


def _dig(payload, path: str):
    """Follow a dotted path (`a.b.0.c`) into parsed JSON; None when it doesn't resolve. A
    deliberately tiny stand-in for a JSONPath dependency — enough for the long-tail GET APIs
    `generic_http` targets."""
    cur = payload
    for part in path.split("."):
        if isinstance(cur, list) and part.isdigit():
            idx = int(part)
            cur = cur[idx] if idx < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def _http_tool(url: str, params: dict[str, str], jsonpath: str) -> BaseTool:
    """A GET against a fixed URL, with `{query}` in any param value filled from the agent's
    argument. Same never-raise contract as the Unsplash tool."""

    @tool
    def fetch(query: str) -> str:
        """Fetch live data from the configured API for `query` and return the result."""
        if not url:
            return "No URL is configured on this HTTP tool — set one in the node's config."
        try:
            r = httpx.get(
                url,
                params={k: v.replace("{query}", query) for k, v in params.items()},
                timeout=10,
            )
        except httpx.HTTPError:
            return "Could not reach the API (network error) — try again in a moment."
        if r.status_code >= 400:
            return f"The API returned an error (HTTP {r.status_code})."
        try:
            payload = r.json()
        except ValueError:
            return _truncate(r.text)
        if jsonpath:
            payload = _dig(payload, jsonpath)
            if payload is None:
                return f"The response had nothing at {jsonpath!r}."
        return _truncate(json.dumps(payload))

    return fetch


_HTTP_DEFS = [
    "_HTTP_URL = {url!r}",
    "_HTTP_PARAMS = {params!r}",
    "_HTTP_JSONPATH = {jsonpath!r}",
    '''@tool
def fetch(query: str) -> str:
    """Fetch live data from the configured API for `query` and return the result."""
    r = httpx.get(
        _HTTP_URL,
        params={k: v.replace("{query}", query) for k, v in _HTTP_PARAMS.items()},
        timeout=10,
    )
    r.raise_for_status()
    payload = r.json()
    for part in filter(None, _HTTP_JSONPATH.split(".")):
        payload = payload[int(part)] if isinstance(payload, list) else payload[part]
    return json.dumps(payload)[:4000]''',
]


@dataclass
class ToolSpec:
    provider: str
    runtime: BaseTool | None  # None → codegen-only (no runtime execution yet)
    bind_schema: dict  # {name, description, input_schema} for model tool-binding
    code_defs: list[str] = field(default_factory=list)  # module-level Python for the tool
    code_ref: str = "web_search"  # the variable referencing the tool in build_graph()
    imports: list[str] = field(default_factory=list)
    # Plural forms — one server (MCP) can yield N tools. When set, these take precedence over
    # the singular `runtime` / `bind_schema` / `code_ref` above; every other provider leaves
    # them None and the node falls back to the single-tool path.
    runtimes: list[BaseTool] | None = None
    bind_schema_list: list[dict] | None = None
    code_ref_list: list[str] | None = None


def _schema_of(t: BaseTool) -> dict:
    fn = convert_to_openai_function(t)
    return {
        "name": fn["name"],
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
    }


def _run_sync(coro):
    """Run an async coroutine to completion on its own event loop, off any ambient loop.

    `compile_graph` is synchronous but is called from inside `async def run` (the runtime),
    so a bare `asyncio.run()` here would raise "cannot be called from a running event loop".
    Running it on a dedicated thread with a fresh loop side-steps that regardless of context."""
    box: dict = {}

    def _runner() -> None:
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:  # re-raise on the caller's thread
            box["error"] = exc

    t = threading.Thread(target=_runner)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box["value"]


# Discovered MCP tools cached per (url, transport, token). `tool_spec()` is called several
# times per compile (bind + code_refs + compile), and discovery is a network round-trip.
_MCP_CACHE: dict[tuple, list[BaseTool]] = {}


def _headers_for(token: str, headers: dict[str, str] | None) -> dict[str, str]:
    """Resolve the request headers for an MCP connection. An explicit `headers` dict (used by
    connectors — e.g. Notion's `Notion-Token`) wins; otherwise a bearer token, if any."""
    if headers:
        return dict(headers)
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def mcp_tools(
    url: str,
    transport: str = "streamable_http",
    *,
    token: str = "",
    headers: dict[str, str] | None = None,
) -> list[BaseTool]:
    """Connect to an MCP server over HTTP and return its tools as LangChain BaseTools.

    Cached per (url, transport, headers) — discovery is a network round-trip and this is called
    several times per compile. Public so the API's connector `/test` + resolution can reuse it."""
    resolved = _headers_for(token, headers)
    key = (url, transport, tuple(sorted(resolved.items())))
    if key not in _MCP_CACHE:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        conn: dict = {"transport": transport, "url": url}
        if resolved:
            conn["headers"] = resolved
        client = MultiServerMCPClient({"server": conn})
        _MCP_CACHE[key] = _run_sync(client.get_tools())
    return _MCP_CACHE[key]


def _mcp_code_defs(transport: str, token: str) -> list[str]:
    """The generated-module snippet that reconstructs the MCP client from env vars.

    Secrets are never serialized — the URL and (optional) bearer read from `os.environ`."""
    headers = (
        '\n        "headers": {"Authorization": f"Bearer {os.environ[\'MCP_TOKEN\']}"},'
        if token
        else ""
    )
    return [
        "_mcp_client = MultiServerMCPClient(\n"
        "    {\n"
        '        "server": {\n'
        f'            "transport": {transport!r},\n'
        '            "url": os.environ["MCP_URL"],'
        f"{headers}\n"
        "        }\n"
        "    }\n"
        ")\n"
        "mcp_tools = asyncio.run(_mcp_client.get_tools())"
    ]


def tool_spec(
    provider: str,
    *,
    max_results: int = 3,
    api_key: str = "",
    http_url: str = "",
    http_params: dict[str, str] | None = None,
    jsonpath: str = "",
    mcp_url: str = "",
    mcp_transport: str = "streamable_http",
    mcp_token: str = "",
    mcp_headers: dict[str, str] | None = None,
    mcp_tool_filter: list[str] | None = None,
    discover: bool = True,
) -> ToolSpec:
    """Resolve a provider name to its ToolSpec.

    `discover=False` skips the live MCP round-trip — the codegen paths (`code_refs`/`codegen`)
    only need the static tool reference and defs, never the discovered tools, so they must not
    require a reachable server at generate time. `mcp_headers` (runtime-injected by a resolved
    connector — e.g. Notion) overrides the bearer-token header when present."""
    if provider == "mcp":
        tools = (
            mcp_tools(mcp_url, mcp_transport, token=mcp_token, headers=mcp_headers)
            if (mcp_url and discover)
            else []
        )
        if mcp_tool_filter:
            allow = set(mcp_tool_filter)
            tools = [t for t in tools if t.name in allow]
        return ToolSpec(
            provider="mcp",
            runtime=None,
            bind_schema={},
            runtimes=tools,
            bind_schema_list=[_schema_of(t) for t in tools],
            code_ref_list=["*mcp_tools"],
            code_defs=_mcp_code_defs(mcp_transport, mcp_token),
            imports=[
                "import asyncio",
                "import os",
                "from langchain_mcp_adapters.client import MultiServerMCPClient",
            ],
        )
    if provider == "images_unsplash":
        runtime = _unsplash_tool(api_key, max_results)
        return ToolSpec(
            provider="images_unsplash",
            runtime=runtime,
            bind_schema=_schema_of(runtime),
            code_defs=[_UNSPLASH_DEFS[0].format(max_results=max_results), _UNSPLASH_DEFS[1]],
            code_ref="search_images",
            imports=[
                "import os",
                "import httpx",
                "from langchain_core.tools import tool",
            ],
        )
    if provider == "generic_http":
        params = http_params or {}
        runtime = _http_tool(http_url, params, jsonpath)
        return ToolSpec(
            provider="generic_http",
            runtime=runtime,
            bind_schema=_schema_of(runtime),
            code_defs=[
                _HTTP_DEFS[0].format(url=http_url),
                _HTTP_DEFS[1].format(params=params),
                _HTTP_DEFS[2].format(jsonpath=jsonpath),
                _HTTP_DEFS[3],
            ],
            code_ref="fetch",
            imports=[
                "import json",
                "import httpx",
                "from langchain_core.tools import tool",
            ],
        )
    if provider == "tavily":
        return ToolSpec(
            provider="tavily",
            runtime=None,  # codegen-only this round
            bind_schema={
                "name": "web_search",
                "description": "Search the web with Tavily and return relevant results.",
                "input_schema": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            code_defs=[f"web_search = TavilySearch(max_results={max_results})"],
            code_ref="web_search",
            imports=["from langchain_tavily import TavilySearch"],
        )
    # demo_search (default) — deterministic, key-free.
    return ToolSpec(
        provider="demo_search",
        runtime=web_search,
        bind_schema=_schema_of(web_search),
        code_defs=[_DEMO_DEF],
        code_ref="web_search",
        imports=["from langchain_core.tools import tool"],
    )
