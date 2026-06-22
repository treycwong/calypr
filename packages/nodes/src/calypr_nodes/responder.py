"""Responder node — the Reflexion actor's first pass (Phase 5b).

It answers, critiques its own answer (what's missing / superfluous), and — with a search
tool wired — asks for the facts it still needs (tool calls). A Tool node then runs those
queries and a Revisor improves the answer. Tools bind exactly like the Agent's (edge-driven)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from calypr_nodes._codegen import assign_str
from calypr_nodes._convert import lc_to_msgs
from calypr_nodes._llm import actor_message
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    register,
)

_RESPONDER_PROMPT = (
    "You are the responder in a Reflexion loop. Answer the question as well as you can, "
    "then critique your own answer — note what is missing or superfluous. If you need "
    "facts, call the web_search tool with focused queries."
)


def _system(cfg: ResponderConfig) -> str:
    if cfg.system_prompt:
        return f"{_RESPONDER_PROMPT}\n\n{cfg.system_prompt}"
    return _RESPONDER_PROMPT


class ResponderConfig(BaseModel):
    model: str = "claude-sonnet-4-5"
    system_prompt: str = ""
    input_channel: str = "messages"
    output_channel: str = "messages"
    temperature: float = 0.0
    max_tokens: int = 1024


@register
class ResponderNode(BaseNode):
    type = "responder"
    meta = NodeMeta(
        label="Responder",
        category="reasoning",
        icon="pen-line",
        description="Reflexion actor: answer, self-critique, and search for gaps.",
    )
    config_model = ResponderConfig

    @classmethod
    def reads(cls, cfg: ResponderConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: ResponderConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def compile(cls, cfg: ResponderConfig, ctx: NodeContext) -> NodeFn:
        if ctx.model is None:
            raise ValueError("Responder node requires a model client in NodeContext")
        model = ctx.model

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            history = lc_to_msgs(state.get(cfg.input_channel) or [])
            msg = await actor_message(
                model,
                model_id=cfg.model,
                system=_system(cfg),
                messages=history,
                tools=ctx.tools or [],
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
            return {cfg.output_channel: [msg]}

        return _run

    @classmethod
    def codegen(cls, cfg: ResponderConfig, fn_name: str, ctx=None) -> CodeFragment:
        refs = ctx.tool_refs if ctx else []
        imports = [
            "from langchain.chat_models import init_chat_model",
            "from langchain_core.messages import SystemMessage",
        ]
        model_expr = f"init_chat_model({cfg.model!r}, temperature={cfg.temperature})"
        if refs:
            model_expr += f".bind_tools([{', '.join(refs)}])"
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """Reflexion responder: answer, self-critique, and search for gaps."""',
            f"    model = {model_expr}",
            f'    messages = state.get("{cfg.input_channel}") or []',
            *assign_str("system", _system(cfg)),
            "    reply = model.invoke([SystemMessage(content=system), *messages])",
            f'    return {{"{cfg.output_channel}": [reply]}}',
        ]
        return CodeFragment(
            fn_name=fn_name, function="\n".join(lines) + "\n", imports=imports
        )
