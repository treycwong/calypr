"""Output / Response node — the terminal; surfaces a state channel as the result."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from calypr_nodes._convert import text_of
from calypr_nodes.registry import BaseNode, NodeContext, NodeFn, NodeMeta, register


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
            messages = state.get(cfg.source_channel) or []
            text = text_of(messages[-1]) if messages else ""
            return {cfg.output_channel: text}

        return _run
