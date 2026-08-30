"""Input / Trigger node — the graph entry; seeds state from the caller's input."""

from __future__ import annotations

import ast
from typing import Any, Literal

from calypr_dsl import Reducer, StateChannel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from calypr_nodes._codegen import assign_str
from calypr_nodes._media import PROMPT_INSTRUCTIONS
from calypr_nodes._parse import (
    docstring,
    last_return_dict_items,
    state_get_keys,
    string_assign,
)
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


def _seeds_a_text_message(value: ast.expr) -> bool:
    """True for Input's signature return value: `[HumanMessage(content=str(<x>))]`.

    The `content=str(...)` wrapper is what separates it from an Upload node, which also returns a
    `HumanMessage` but with a list of multimodal content blocks. Used as a structural fallback so
    a user who rewrites the docstring still gets an Input node back rather than a Code node —
    Input's whole config is recoverable from structure, so nothing is guessed."""
    if not isinstance(value, ast.List) or not value.elts:
        return False
    call = value.elts[0]
    if not (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Name)
        and call.func.id == "HumanMessage"
    ):
        return False
    return any(
        kw.arg == "content"
        and isinstance(kw.value, ast.Call)
        and isinstance(kw.value.func, ast.Name)
        and kw.value.func.id == "str"
        for kw in call.keywords
    )


class InputConfig(BaseModel):
    mode: Literal["chat", "api", "form"] = "chat"
    # In chat mode, the raw user text arrives on `input_channel` and is appended to
    # `target_channel` as a Human message.
    input_channel: str = "input"
    target_channel: str = "messages"
    prompt_instructions: str = Field(
        default="",
        description=(
            "Criteria applied to every generative block downstream — written once, here, instead "
            "of on each block. The Image and Video blocks append it to their prompt after their "
            "own settings; every other block ignores it. Empty means the graph behaves, and "
            "generates code, exactly as it did before."
        ),
    )


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
        # The instructions channel appears only when there is something to put in it, so a graph
        # that doesn't use the field declares nothing new and generates the code it always did.
        # `validate.py` checks every written channel against the declared state, so this and
        # `channels()` below have to agree.
        if cfg.prompt_instructions.strip():
            return [cfg.target_channel, PROMPT_INSTRUCTIONS]
        return [cfg.target_channel]

    @classmethod
    def channels(cls, cfg: InputConfig) -> list[StateChannel]:
        if not cfg.prompt_instructions.strip():
            return []
        # Declared by the writer, which is what lets every consumer read it without any template
        # being edited — `graph_channels` unions node-owned channels into the graph's state.
        return [StateChannel(key=PROMPT_INSTRUCTIONS, type="string", reducer=Reducer.last)]

    @classmethod
    def compile(cls, cfg: InputConfig, ctx: NodeContext) -> NodeFn:
        instructions = cfg.prompt_instructions.strip()

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            raw = state.get(cfg.input_channel)
            if raw is None or raw == "":
                return {}
            update: dict[str, Any] = {cfg.target_channel: [HumanMessage(content=str(raw))]}
            if instructions:
                update[PROMPT_INSTRUCTIONS] = instructions
            return update

        return _run

    @classmethod
    def codegen(cls, cfg: InputConfig, fn_name: str, ctx=None) -> CodeFragment:
        instructions = cfg.prompt_instructions.strip()
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            f'    """{_DOCSTRING}"""',
            f'    text = state.get("{cfg.input_channel}")',
            "    if not text:",
            "        return {}",
        ]
        if instructions:
            # Emitted as a named literal rather than inline in the return dict, so `parse` can
            # read it back with `string_assign` and a reader can edit it without hunting through
            # a dict — the same shape the Image block uses for its `style`.
            lines += assign_str("instructions", instructions)
            lines.append(
                f'    return {{"{cfg.target_channel}": [HumanMessage(content=str(text))], '
                f'"{PROMPT_INSTRUCTIONS}": instructions}}'
            )
        else:
            lines.append(
                f'    return {{"{cfg.target_channel}": [HumanMessage(content=str(text))]}}'
            )
        return CodeFragment(
            fn_name=fn_name,
            function="\n".join(lines) + "\n",
            imports=["from langchain_core.messages import HumanMessage"],
        )

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> InputConfig | None:
        """Recover an Input node from its generated function: it reads
        `state.get("<input_channel>")` and returns `{"<target_channel>": [HumanMessage(...)]}`.

        Keyed on the stable docstring the generator emits, falling back to the structural
        signature (`[HumanMessage(content=str(...))]`) when the docstring has been rewritten —
        precise enough to never claim another node type that also seeds a `HumanMessage`
        (e.g. Upload, whose content is a list of blocks).

        **Reads the return with `last_return_dict_items`, not `last_return_dict`.** The latter
        matches only a *single*-key dict, and an Input node carrying Prompt Instructions returns
        two — so using it would make every such node fail to parse and degrade to a `code` node
        on the way back from the editor. The message channel is found by shape rather than by
        position, which is also what keeps the two keys from being confused for each other.
        """
        fn = ctx.func
        if fn is None:
            return None
        items = last_return_dict_items(fn)
        keys = state_get_keys(fn)
        if not items or not keys:
            return None
        seeded = next((pair for pair in items if _seeds_a_text_message(pair[1])), None)
        if docstring(fn) != _DOCSTRING and seeded is None:
            return None
        # A rewritten docstring leaves only the structural match; the canonical docstring alone is
        # enough when the return has been reshaped by hand.
        target = seeded[0] if seeded is not None else items[0][0]
        cfg = InputConfig(input_channel=keys[0], target_channel=target)
        if any(key == PROMPT_INSTRUCTIONS for key, _ in items):
            if (instructions := string_assign(fn, "instructions")) is not None:
                cfg.prompt_instructions = instructions
        return cfg
