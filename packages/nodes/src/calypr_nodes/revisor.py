"""Revisor node — the Reflexion actor's improvement pass (Phase 5b).

It rewrites the answer using the tool results from the previous turn, may search again, and
counts revisions. Its `routing()` makes the loop bounded: keep revising (→ Tools → Revisor)
until the `revision_count` reaches `max_revisions`, then finish (→ Output). The counter +
the compiler's recursion_limit guarantee termination."""

from __future__ import annotations

import ast
from typing import Any

from calypr_dsl import Reducer, StateChannel
from pydantic import BaseModel

from calypr_nodes._codegen import assign_str
from calypr_nodes._convert import lc_to_msgs
from calypr_nodes._llm import actor_message
from calypr_nodes._parse import docstring, llm_actor_fields
from calypr_nodes.registry import (
    PLATFORM_DEFAULT_MODEL,
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    effective_model,
    model_for_node,
    register,
)

_DOCSTRING = "Reflexion revisor: improve using tool results; may search again."

_REVISOR_PROMPT = (
    "You are the revisor in a Reflexion loop. Improve the previous answer using the new "
    "search results and your earlier critique. Cite sources you used. If important facts "
    "are still missing, call the web_search tool again."
)
_COUNT = "revision_count"


def _system(cfg: RevisorConfig) -> str:
    if cfg.system_prompt:
        return f"{_REVISOR_PROMPT}\n\n{cfg.system_prompt}"
    return _REVISOR_PROMPT


class RevisorConfig(BaseModel):
    #: Empty = inherit (workspace default → PLATFORM_DEFAULT_MODEL). See `effective_model`.
    model: str = ""
    system_prompt: str = ""
    input_channel: str = "messages"
    output_channel: str = "messages"
    temperature: float = 0.0
    max_tokens: int = 1024
    max_revisions: int = 2


@register
class RevisorNode(BaseNode):
    type = "revisor"
    meta = NodeMeta(
        label="Revisor",
        category="reasoning",
        icon="pencil",
        description="Reflexion actor: revise with tool results; loop until the budget is spent.",
    )
    config_model = RevisorConfig

    @classmethod
    def reads(cls, cfg: RevisorConfig) -> list[str]:
        return [cfg.input_channel, _COUNT]

    @classmethod
    def writes(cls, cfg: RevisorConfig) -> list[str]:
        return [cfg.output_channel, _COUNT]

    @classmethod
    def channels(cls, cfg: RevisorConfig) -> list[StateChannel]:
        # The loop counter must be declared (last-write) or the bounded loop never bounds.
        return [StateChannel(key=_COUNT, type="number", reducer=Reducer.last)]

    @classmethod
    def compile(cls, cfg: RevisorConfig, ctx: NodeContext) -> NodeFn:
        model_id = effective_model(ctx, cfg.model)
        model = model_for_node(ctx, cfg.model)

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            history = lc_to_msgs(state.get(cfg.input_channel) or [])
            msg = await actor_message(
                model,
                model_id=model_id,
                system=_system(cfg),
                messages=history,
                tools=ctx.tools or [],
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
            return {cfg.output_channel: [msg], _COUNT: state.get(_COUNT, 0) + 1}

        return _run

    @classmethod
    def routing(cls, cfg: RevisorConfig, ctx: NodeContext):
        """Bounded loop: revise again until the revision budget is spent, then finish."""
        max_revisions = cfg.max_revisions

        def _route(state: dict[str, Any]) -> str:
            return "revise" if state.get(_COUNT, 0) < max_revisions else "done"

        return _route

    @classmethod
    def codegen(cls, cfg: RevisorConfig, fn_name: str, ctx=None) -> CodeFragment:
        refs = ctx.tool_refs if ctx else []
        imports = [
            "from langchain.chat_models import init_chat_model",
            "from langchain_core.messages import SystemMessage",
        ]
        model_expr = (
            f"init_chat_model({(cfg.model or PLATFORM_DEFAULT_MODEL)!r}, "
            f"temperature={cfg.temperature})"
        )
        if refs:
            model_expr += f".bind_tools([{', '.join(refs)}])"
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """Reflexion revisor: improve using tool results; may search again."""',
            f"    model = {model_expr}",
            f'    messages = state.get("{cfg.input_channel}") or []',
            *assign_str("system", _system(cfg)),
            "    reply = model.invoke([SystemMessage(content=system), *messages])",
            f'    count = state.get("{_COUNT}", 0) + 1',
            f'    return {{"{cfg.output_channel}": [reply], "{_COUNT}": count}}',
            "",
            "",
            f"def route_{fn_name}(state: State) -> str:",
            '    """Loop back to revise until the revision budget is spent."""',
            f'    if state.get("{_COUNT}", 0) < {cfg.max_revisions}:',
            '        return "revise"',
            '    return "done"',
        ]
        return CodeFragment(
            fn_name=fn_name,
            function="\n".join(lines) + "\n",
            imports=imports,
            routing=True,
        )

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> RevisorConfig | None:
        """Recover a Reflexion Revisor: the LLM-actor shape plus the revision budget, read from
        the `route_<ref>` companion's `if state.get("revision_count", 0) < <max_revisions>`."""
        fn = ctx.func
        if fn is None or docstring(fn) != _DOCSTRING:
            return None
        fields = llm_actor_fields(fn, _REVISOR_PROMPT)
        if fields is None:
            return None
        cfg = RevisorConfig(**fields)
        route_fn = ctx.defs.get(f"route_{ctx.ref_name}")
        if isinstance(route_fn, ast.FunctionDef):
            for cmp in (n for n in ast.walk(route_fn) if isinstance(n, ast.Compare)):
                right = cmp.comparators[0] if cmp.comparators else None
                if isinstance(right, ast.Constant) and isinstance(right.value, int):
                    cfg.max_revisions = right.value
                    break
        return cfg
