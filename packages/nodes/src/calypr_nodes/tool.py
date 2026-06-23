"""Tool node — executes the tool calls an agent emits, then loops back (Phase 5).

It's LangGraph's `ToolNode` over a provider from the catalog: it reads the latest
AIMessage's tool calls from `messages`, runs the matching tool, and appends the results as
ToolMessages. An agent/responder/revisor wired *to* this node both binds its tool (the
compiler resolves the schema) and routes here when it asks for a tool — the canonical ReAct
loop. The provider is a dropdown (demo_search now; Tavily is codegen-only)."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode as LCToolNode
from pydantic import BaseModel

from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    CodegenContext,
    NodeContext,
    NodeFn,
    NodeMeta,
    register,
)
from calypr_nodes.tools_catalog import tool_spec


class ToolConfig(BaseModel):
    provider: Literal["demo_search", "tavily"] = "demo_search"
    api_key: str = ""  # runtime-only; never embedded in generated code
    max_results: int = 3


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

    @classmethod
    def bind_schemas(cls, cfg: ToolConfig) -> list[dict]:
        """The tool schemas a connected LLM node should bind."""
        return [tool_spec(cfg.provider, max_results=cfg.max_results).bind_schema]

    @classmethod
    def code_refs(cls, cfg: ToolConfig) -> list[str]:
        """The tool variable name(s) a connected LLM node should `bind_tools([...])`."""
        return [tool_spec(cfg.provider, max_results=cfg.max_results).code_ref]

    @classmethod
    def compile(cls, cfg: ToolConfig, ctx: NodeContext) -> NodeFn:
        spec = tool_spec(cfg.provider, max_results=cfg.max_results)
        if spec.runtime is None:
            # Codegen-only provider: answer each pending tool call with an explanatory
            # ToolMessage instead of raising — raising would leave the assistant's tool_calls
            # unanswered and corrupt the thread for the next turn.
            note = (
                f"{cfg.provider!r} execution is codegen-only here — generate the code and "
                "run it with your API key, or switch this Tool node to 'demo_search' to "
                "run on the canvas."
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

        async def _run(state: dict[str, Any], config) -> dict[str, Any]:
            messages = state.get("messages") or []
            last = messages[-1] if messages else None
            if not getattr(last, "tool_calls", None):
                return {}  # nothing to run (e.g. the actor asked no tool this turn)
            return await lc_node.ainvoke(state, config)

        return _run

    @classmethod
    def codegen(
        cls, cfg: ToolConfig, fn_name: str, ctx: CodegenContext | None = None
    ) -> CodeFragment:
        spec = tool_spec(cfg.provider, max_results=cfg.max_results)
        imports = ["from langgraph.prebuilt import ToolNode", *spec.imports]
        defs = "\n\n".join(spec.code_defs)
        node_line = f"{fn_name} = ToolNode([{spec.code_ref}])"
        function = f"{defs}\n\n\n{node_line}" if defs else node_line
        return CodeFragment(fn_name=fn_name, function=function, imports=imports)
