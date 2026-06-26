"""Output / Response node — the terminal; surfaces a state channel as the result."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from calypr_nodes._convert import text_of
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    register,
)


class OutputConfig(BaseModel):
    # Read the last message from `source_channel` and write its text to `output_channel`.
    source_channel: str = "messages"
    output_channel: str = "output"
    stream: bool = True


@register
class OutputNode(BaseNode):
    type = "output"
    meta = NodeMeta(
        label="Output",
        category="io",
        icon="log-out",
        description="Terminal; returns the selected channel as the run result.",
    )
    config_model = OutputConfig

    @classmethod
    def reads(cls, cfg: OutputConfig) -> list[str]:
        return [cfg.source_channel]

    @classmethod
    def writes(cls, cfg: OutputConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def compile(cls, cfg: OutputConfig, ctx: NodeContext) -> NodeFn:
        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            value = state.get(cfg.source_channel)
            if isinstance(value, str):  # a plain channel (e.g. retrieved context)
                text = value
            else:  # a messages list — surface the last message's text
                text = text_of(value[-1]) if value else ""
            return {cfg.output_channel: text}

        return _run

    @classmethod
    def codegen(cls, cfg: OutputConfig, fn_name: str, ctx=None) -> CodeFragment:
        fn = (
            f"def {fn_name}(state: State) -> dict:\n"
            f'    """Return the selected channel as the result."""\n'
            f'    value = state.get("{cfg.source_channel}")\n'
            f"    if isinstance(value, str):\n"
            f"        text = value\n"
            f"    else:\n"
            f'        text = value[-1].content if value else ""\n'
            f'    return {{"{cfg.output_channel}": text}}\n'
        )
        return CodeFragment(fn_name=fn_name, function=fn)
