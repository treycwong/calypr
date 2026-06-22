"""Tool catalog — the providers a Tool node can execute or generate (Phase 5).

Each provider yields everything the rest of the engine needs: a LangChain `BaseTool` to
execute (or None for codegen-only providers), a unified bind-schema so an LLM node can
`model.bind_tools(...)`/`stream(tools=...)`, and the Python (defs + a reference + imports)
to emit in the owned, standalone module. `demo_search` runs with no key or network so the
canvas, tests, and keyless playground stay deterministic; `tavily` is codegen-only for now."""

from __future__ import annotations

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


def _schema_of(t: BaseTool) -> dict:
    fn = convert_to_openai_function(t)
    return {
        "name": fn["name"],
        "description": fn.get("description", ""),
        "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
    }


def tool_spec(provider: str, *, max_results: int = 3) -> ToolSpec:
    """Resolve a provider name to its ToolSpec."""
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
