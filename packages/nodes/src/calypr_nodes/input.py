"""Input / Trigger node — the graph entry; seeds state from the caller's input."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from calypr_nodes._parse import docstring, last_return_dict, state_get_keys
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    register,
)

_DOCSTRING = "Seed the conversation from the caller's input."


class InputConfig(BaseModel):
    mode: Literal["chat", "api", "form"] = "chat"
    # In chat mode, the raw user text arrives on `input_channel` and is appended to
    # `target_channel` as a Human message.
    input_channel: str = "input"
    target_channel: str = "messages"


@register
class InputNode(BaseNode):
    type = "input"
    meta = NodeMeta(
        label="Input",
        category="io",
        icon="log-in",
        description="Entry point; seeds the graph state from the caller's input.",
    )
    config_model = InputConfig

    @classmethod
    def reads(cls, cfg: InputConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: InputConfig) -> list[str]:
        return [cfg.target_channel]

    @classmethod
    def compile(cls, cfg: InputConfig, ctx: NodeContext) -> NodeFn:
        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            raw = state.get(cfg.input_channel)
            if raw is None or raw == "":
                return {}
            return {cfg.target_channel: [HumanMessage(content=str(raw))]}

        return _run

    @classmethod
    def codegen(cls, cfg: InputConfig, fn_name: str, ctx=None) -> CodeFragment:
        fn = (
            f"def {fn_name}(state: State) -> dict:\n"
            f'    """Seed the conversation from the caller\'s input."""\n'
            f'    text = state.get("{cfg.input_channel}")\n'
            f"    if not text:\n"
            f"        return {{}}\n"
            f'    return {{"{cfg.target_channel}": [HumanMessage(content=str(text))]}}\n'
        )
        return CodeFragment(
            fn_name=fn_name,
            function=fn,
            imports=["from langchain_core.messages import HumanMessage"],
        )

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> InputConfig | None:
        """Recover an Input node from its generated function: it reads
        `state.get("<input_channel>")` and returns `{"<target_channel>": [HumanMessage(...)]}`.

        Keyed on the stable docstring the generator emits — precise enough to never claim
        another node type that also seeds a `HumanMessage` (e.g. Upload). Hardening against a
        user-rewritten docstring is Week-7 edit-survival work."""
        fn = ctx.func
        if fn is None or docstring(fn) != _DOCSTRING:
            return None
        found = last_return_dict(fn)
        keys = state_get_keys(fn)
        if found is None or not keys:
            return None
        return InputConfig(input_channel=keys[0], target_channel=found[0])
