"""Output / Response node — the terminal; surfaces a state channel as the result."""

from __future__ import annotations

import ast
from typing import Any

from pydantic import BaseModel

from calypr_nodes._convert import text_of
from calypr_nodes._parse import docstring, has_call, last_return_dict, state_get_keys
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    register,
)

_DOCSTRING = "Return the selected channel as the result."


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

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> OutputConfig | None:
        """Recover an Output node: it reads `state.get("<source_channel>")`, narrows the value
        with `isinstance(value, str)`, and returns `{"<output_channel>": text}`.

        Keyed on the generator's stable docstring, falling back to the structural signature when
        it has been rewritten: an `isinstance` narrowing plus a *plain* return value. Every other
        node that narrows with `isinstance` (Image, Voice) returns a message **list**, so the
        non-list return is what makes the fallback safe. Output's whole config is recoverable
        from structure, so nothing is guessed."""
        fn = ctx.func
        if fn is None:
            return None
        found = last_return_dict(fn)
        keys = state_get_keys(fn)
        if found is None or not keys:
            return None
        structural = not isinstance(found[1], ast.List) and has_call(fn, "isinstance")
        if docstring(fn) != _DOCSTRING and not structural:
            return None
        return OutputConfig(source_channel=keys[0], output_channel=found[0])
