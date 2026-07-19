"""Tool catalog — the providers a Tool node can execute or generate (Phase 5).

Each provider yields everything the rest of the engine needs: a LangChain `BaseTool` to
execute (or None for codegen-only providers), a unified bind-schema so an LLM node can
`model.bind_tools(...)`/`stream(tools=...)`, and the Python (defs + a reference + imports)
to emit in the owned, standalone module. `demo_search` runs with no key or network so the
canvas, tests, and keyless playground stay deterministic; `tavily` is codegen-only for now."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field

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
