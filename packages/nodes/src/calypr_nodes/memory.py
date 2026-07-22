"""Memory node — make a model-based / learning agent's memory explicit (Phase 4).

Two operations now: `buffer` appends the latest message to a named memory channel (a
running list; model-free and deterministic), and `summary` condenses the conversation into
a memory string via the model. Thread memory already comes from the checkpointer; this node
makes it a visible, owned step. Semantic/pgvector memory shares the RAG work in Phase 5."""

from __future__ import annotations

from typing import Any, Literal

from calypr_dsl import Reducer, StateChannel
from calypr_model import Msg, Role
from pydantic import BaseModel

from calypr_nodes._codegen import assign_str
from calypr_nodes._llm import collect_text
from calypr_nodes._parse import (
    calls_named,
    docstring,
    kwarg_const,
    return_dict_key,
    state_get_keys,
    str_const,
)
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

_BUFFER_DOC = "Append the latest message to the memory buffer."
_SUMMARY_DOC = "Summarise the conversation into long-term memory."

_SUMMARY_PROMPT = (
    "Summarise the conversation so far in a few sentences, keeping facts and decisions "
    "that matter for later. Reply with the summary only."
)


class MemoryConfig(BaseModel):
    operation: Literal["buffer", "summary"] = "buffer"
    input_channel: str = "messages"
    memory_channel: str = "memory"
    #: Empty = inherit (workspace default → PLATFORM_DEFAULT_MODEL). See `effective_model`.
    model: str = ""  # used by `summary`
    temperature: float = 0.0


def _last_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        last = value[-1]
        return getattr(last, "content", str(last))
    return ""


def _transcript(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(getattr(m, "content", str(m)) for m in value)
    return _last_text(value)


@register
class MemoryNode(BaseNode):
    type = "memory"
    meta = NodeMeta(
        label="Memory",
        category="memory",
        icon="database",
        description="Remember across turns — append to a buffer or summarise the chat.",
    )
    config_model = MemoryConfig

    @classmethod
    def reads(cls, cfg: MemoryConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: MemoryConfig) -> list[str]:
        return [cfg.memory_channel]

    @classmethod
    def channels(cls, cfg: MemoryConfig) -> list[StateChannel]:
        return [StateChannel(key=cfg.memory_channel, type="list", reducer=Reducer.append)]

    @classmethod
    def compile(cls, cfg: MemoryConfig, ctx: NodeContext) -> NodeFn:
        if cfg.operation == "buffer":

            async def _buffer(state: dict[str, Any]) -> dict[str, Any]:
                latest = _last_text(state.get(cfg.input_channel))
                return {cfg.memory_channel: [latest]}

            return _buffer

        model_id = effective_model(ctx, cfg.model)
        model = model_for_node(ctx, cfg.model)

        async def _summary(state: dict[str, Any]) -> dict[str, Any]:
            transcript = _transcript(state.get(cfg.input_channel))
            summary = await collect_text(
                model,
                model_id=model_id,
                system=_SUMMARY_PROMPT,
                messages=[Msg(role=Role.user, content=transcript)],
                temperature=cfg.temperature,
            )
            # Memory is a list of remembered items (append-reducer), like the buffer.
            return {cfg.memory_channel: [summary]}

        return _summary

    @classmethod
    def codegen(cls, cfg: MemoryConfig, fn_name: str, ctx=None) -> CodeFragment:
        if cfg.operation == "buffer":
            lines = [
                f"def {fn_name}(state: State) -> dict:",
                '    """Append the latest message to the memory buffer."""',
                f'    messages = state.get("{cfg.input_channel}") or []',
                '    latest = messages[-1].content if messages else ""',
                f'    return {{"{cfg.memory_channel}": [latest]}}',
            ]
            return CodeFragment(fn_name=fn_name, function="\n".join(lines) + "\n")

        imports = [
            "from langchain.chat_models import init_chat_model",
            "from langchain_core.messages import HumanMessage, SystemMessage",
        ]
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """Summarise the conversation into long-term memory."""',
            f"    model = init_chat_model({(cfg.model or PLATFORM_DEFAULT_MODEL)!r}, "
            f"temperature={cfg.temperature})",
            f'    messages = state.get("{cfg.input_channel}") or []',
            '    transcript = "\\n".join(getattr(m, "content", str(m)) for m in messages)',
            *assign_str("system", _SUMMARY_PROMPT),
            "    summary = model.invoke(",
            "        [SystemMessage(content=system), HumanMessage(content=transcript)]",
            "    ).content",
            f'    return {{"{cfg.memory_channel}": [summary]}}',
        ]
        return CodeFragment(
            fn_name=fn_name, function="\n".join(lines) + "\n", imports=imports
        )

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> MemoryConfig | None:
        """Recover a Memory node. The docstring selects the operation: `buffer` just appends
        the latest message; `summary` runs an LLM over the transcript (so model + temperature
        are recovered too). Both read `state.get("<input_channel>")` and write one channel."""
        fn = ctx.func
        if fn is None:
            return None
        doc = docstring(fn)
        if doc not in (_BUFFER_DOC, _SUMMARY_DOC):
            return None
        keys = state_get_keys(fn)
        memory_channel = return_dict_key(fn)
        if not keys or memory_channel is None:
            return None
        if doc == _BUFFER_DOC:
            return MemoryConfig(
                operation="buffer", input_channel=keys[0], memory_channel=memory_channel
            )
        calls = calls_named(fn, "init_chat_model")
        model = str_const(calls[0].args[0]) if calls and calls[0].args else None
        temperature = kwarg_const(calls[0], "temperature") if calls else None
        cfg = MemoryConfig(
            operation="summary", input_channel=keys[0], memory_channel=memory_channel
        )
        if model is not None:
            cfg.model = model
        if isinstance(temperature, (int, float)):
            cfg.temperature = float(temperature)
        return cfg
