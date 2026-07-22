"""Tool node — executes the tool calls an agent emits, then loops back (Phase 5).

It's LangGraph's `ToolNode` over a provider from the catalog: it reads the latest
AIMessage's tool calls from `messages`, runs the matching tool, and appends the results as
ToolMessages. An agent/responder/revisor wired *to* this node both binds its tool (the
compiler resolves the schema) and routes here when it asks for a tool — the canonical ReAct
loop. The provider is a dropdown (demo_search, Tavily, Unsplash, a generic GET, or MCP)."""

from __future__ import annotations

import ast
from typing import Any, Literal

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode as LCToolNode
from pydantic import BaseModel

from calypr_nodes._parse import dict_lookup, kwarg_const, str_const
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    CodegenContext,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    register,
)
from calypr_nodes.tools_catalog import tool_spec


class ToolConfig(BaseModel):
    provider: Literal["demo_search", "tavily", "mcp", "images_unsplash", "generic_http"] = (
        "demo_search"
    )
    api_key: str = ""  # runtime-only; never embedded in generated code
    max_results: int = 3
    # HTTP-only — ignored unless provider == "generic_http". A GET against a fixed URL, with
    # `{query}` in any param value filled from the agent's tool argument. GET only in v1.
    http_url: str = ""
    http_method: Literal["GET"] = "GET"
    http_params: dict[str, str] = {}
    jsonpath: str = ""  # dotted path into the response JSON (blank = the whole payload)
    # MCP-only — ignored unless provider == "mcp". An MCP server's tools become available to
    # any connected LLM through the same edge walk as demo_search/tavily.
    mcp_url: str = ""  # HTTP endpoint of the MCP server
    mcp_transport: Literal["streamable_http", "sse"] = "streamable_http"
    mcp_token: str = ""  # runtime-only bearer; never embedded in generated code
    mcp_tool_filter: list[str] = []  # subset of the server's tools to bind (empty = all)
    # A vault handle for a saved connector (Tier A/B). The canvas stores only this ref; the
    # server resolves it to url + headers at run time (never a secret in the DSL).
    mcp_connector_ref: str = ""
    # Runtime-only, server-injected connection headers from a resolved connector (e.g. Notion's
    # `Notion-Token`). Never set by the client, never serialized to codegen.
    mcp_headers: dict[str, str] = {}


def _const(ctx: NodeParseContext, name: str, default):
    """The literal value of a module-level `name = <literal>` the HTTP providers emit beside
    their tool function (`_HTTP_URL`, `_UNSPLASH_RESULTS`, …), else `default`.

    The generators hoist these out of the function body precisely so the inverse is a one-liner
    — the same trick `parse()` uses to read the MCP client's `_mcp_client` assignment."""
    node = ctx.defs.get(name)
    if not isinstance(node, ast.Assign):
        return default
    try:
        return ast.literal_eval(node.value)
    except (ValueError, SyntaxError):
        return default


@register
class ToolsNode(BaseNode):
    type = "tool"
    meta = NodeMeta(
        label="Tools",
        category="tools",
        icon="wrench",
        description="Run the tools an agent calls (web search now) and loop back.",
    )
    config_model = ToolConfig

    @classmethod
    def reads(cls, cfg: ToolConfig) -> list[str]:
        return ["messages"]

    @classmethod
    def writes(cls, cfg: ToolConfig) -> list[str]:
        return ["messages"]

    @staticmethod
    def _spec(cfg: ToolConfig, *, discover: bool = True):
        return tool_spec(
            cfg.provider,
            max_results=cfg.max_results,
            api_key=cfg.api_key,
            http_url=cfg.http_url,
            http_params=cfg.http_params,
            jsonpath=cfg.jsonpath,
            mcp_url=cfg.mcp_url,
            mcp_transport=cfg.mcp_transport,
            mcp_token=cfg.mcp_token,
            mcp_headers=cfg.mcp_headers,
            mcp_tool_filter=cfg.mcp_tool_filter,
            discover=discover,
        )

    @classmethod
    def bind_schemas(cls, cfg: ToolConfig) -> list[dict]:
        """The tool schemas a connected LLM node should bind (N of them for an MCP server)."""
        spec = cls._spec(cfg)
        if spec.bind_schema_list is not None:
            return spec.bind_schema_list
        return [spec.bind_schema]

    @classmethod
    def code_refs(cls, cfg: ToolConfig) -> list[str]:
        """The tool variable name(s) a connected LLM node should `bind_tools([...])`."""
        spec = cls._spec(cfg, discover=False)  # codegen ref is static — never hit the server
        if spec.code_ref_list is not None:
            return spec.code_ref_list
        return [spec.code_ref]

    @staticmethod
    def _own_calls_only(state: dict[str, Any], owned: set[str]) -> dict[str, Any] | None:
        """`state` narrowed to the pending tool calls this node's own tools can serve, or None
        when there are none to run.

        An agent wired to several Tool nodes can emit calls for two of them in one turn, and
        the router fans out to both. Each node must answer *only* its own calls: handing the
        untouched message to `ToolNode` would make it fail the sibling's calls by name and
        double-answer the same `tool_call_id`."""
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        calls = getattr(last, "tool_calls", None)
        if not calls:
            return None  # nothing to run (e.g. the actor asked no tool this turn)
        mine = [c for c in calls if c.get("name") in owned]
        if not mine:
            return None
        if len(mine) == len(calls):
            return state  # sole owner — pass the state through untouched
        return {**state, "messages": [*messages[:-1], last.model_copy(update={"tool_calls": mine})]}

    @classmethod
    def compile(cls, cfg: ToolConfig, ctx: NodeContext) -> NodeFn:
        spec = cls._spec(cfg)
        if spec.runtimes is not None:
            # MCP: N remote tools over one ToolNode. Empty (no URL / discovery yielded
            # nothing) falls through to the codegen-only note below.
            if spec.runtimes:
                lc_node = LCToolNode(spec.runtimes)
                owned = {t.name for t in spec.runtimes}

                async def _run_mcp(state: dict[str, Any], config) -> dict[str, Any]:
                    scoped = cls._own_calls_only(state, owned)
                    if scoped is None:
                        return {}
                    return await lc_node.ainvoke(scoped, config)

                return _run_mcp
        if spec.runtime is None:
            # Nothing to execute — answer each pending tool call with an explanatory
            # ToolMessage instead of raising, since raising would leave the assistant's
            # tool_calls unanswered and corrupt the thread for the next turn. Now that every
            # provider has a runtime, the only way here is an MCP node whose server is
            # unreachable or exposed no tools.
            note = (
                "This tool could not run: its MCP server is unreachable or exposed no tools. "
                "Tell the user to check the server URL and connection in Settings."
                if cfg.provider == "mcp"
                else f"{cfg.provider!r} cannot run on the canvas — generate the code and run "
                "it locally, or switch this Tool node to 'demo_search'."
            )

            async def _unsupported(state: dict[str, Any]) -> dict[str, Any]:
                messages = state.get("messages") or []
                last = messages[-1] if messages else None
                calls = getattr(last, "tool_calls", None) or []
                return {
                    "messages": [
                        ToolMessage(
                            content=note,
                            tool_call_id=tc["id"],
                            name=tc.get("name", cfg.provider),
                        )
                        for tc in calls
                    ]
                }

            return _unsupported

        lc_node = LCToolNode([spec.runtime])
        owned = {spec.runtime.name}

        async def _run(state: dict[str, Any], config) -> dict[str, Any]:
            scoped = cls._own_calls_only(state, owned)
            if scoped is None:
                return {}
            return await lc_node.ainvoke(scoped, config)

        return _run

    @classmethod
    def codegen(
        cls, cfg: ToolConfig, fn_name: str, ctx: CodegenContext | None = None
    ) -> CodeFragment:
        spec = cls._spec(cfg, discover=False)  # generated code reads env — no live discovery
        imports = ["from langgraph.prebuilt import ToolNode", *spec.imports]
        defs = "\n\n".join(spec.code_defs)
        refs = spec.code_ref_list if spec.code_ref_list is not None else [spec.code_ref]
        node_line = f"{fn_name} = ToolNode([{', '.join(refs)}])"
        function = f"{defs}\n\n\n{node_line}" if defs else node_line
        return CodeFragment(fn_name=fn_name, function=function, imports=imports)

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> ToolConfig | None:
        """Recover a Tool node — the only node emitted as an *assignment*
        (`node_x = ToolNode([...])`) rather than a function. The tool references discriminate
        the provider: `*mcp_tools` → an MCP server (transport + whether a bearer is used come
        from the emitted client); a `web_search` reference resolves through its own definition —
        an `@tool` function is `demo_search`, a `TavilySearch(...)` assignment is `tavily`.

        Runtime-only fields (`api_key`, `mcp_url`/`mcp_token` values, connector refs) are never
        serialized into code and come back as defaults — codegen-lossless, since generation
        keys only on the provider, transport, and whether a token is present."""
        assign = ctx.assign
        if assign is None or not isinstance(assign.value, ast.Call):
            return None
        call = assign.value
        if not (isinstance(call.func, ast.Name) and call.func.id == "ToolNode"):
            return None
        if not call.args or not isinstance(call.args[0], ast.List):
            return None
        elts = call.args[0].elts

        if any(isinstance(e, ast.Starred) for e in elts):  # ToolNode([*mcp_tools]) → MCP
            client = ctx.defs.get("_mcp_client")
            client_val = client.value if isinstance(client, ast.Assign) else None
            transport = str_const(dict_lookup(client_val, "transport")) or "streamable_http"
            has_headers = dict_lookup(client_val, "headers") is not None
            return ToolConfig(
                provider="mcp",
                mcp_transport=transport,
                mcp_token="x" if has_headers else "",  # presence only; the value reads from env
            )

        ref = elts[0].id if elts and isinstance(elts[0], ast.Name) else None
        defn = ctx.defs.get(ref or "")
        if ref == "search_images" and isinstance(defn, ast.FunctionDef):
            return ToolConfig(
                provider="images_unsplash",
                max_results=_const(ctx, "_UNSPLASH_RESULTS", 3),
            )
        if ref == "fetch" and isinstance(defn, ast.FunctionDef):
            return ToolConfig(
                provider="generic_http",
                http_url=_const(ctx, "_HTTP_URL", ""),
                http_params=_const(ctx, "_HTTP_PARAMS", {}),
                jsonpath=_const(ctx, "_HTTP_JSONPATH", ""),
            )
        if isinstance(defn, ast.FunctionDef):  # @tool def web_search(...) → demo_search
            return ToolConfig(provider="demo_search")
        if (
            isinstance(defn, ast.Assign)
            and isinstance(defn.value, ast.Call)
            and isinstance(defn.value.func, ast.Name)
            and defn.value.func.id == "TavilySearch"
        ):
            mr = kwarg_const(defn.value, "max_results")
            return ToolConfig(provider="tavily", max_results=mr if isinstance(mr, int) else 3)
        return None
