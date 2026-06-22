"""Memory node — make a model-based / learning agent's memory explicit (Phase 4).

Two operations now: `buffer` appends the latest message to a named memory channel (a
running list; model-free and deterministic), and `summary` condenses the conversation into
a memory string via the model. Thread memory already comes from the checkpointer; this node
makes it a visible, owned step. Semantic/pgvector memory shares the RAG work in Phase 5."""

from __future__ import annotations

from typing import Any, Literal

from calypr_model import Msg, Role
from pydantic import BaseModel

from calypr_nodes._codegen import assign_str
from calypr_nodes._llm import collect_text
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    register,
)

_SUMMARY_PROMPT = (
    "Summarise the conversation so far in a few sentences, keeping facts and decisions "
    "that matter for later. Reply with the summary only."
)


class MemoryConfig(BaseModel):
    operation: Literal["buffer", "summary"] = "buffer"
    input_channel: str = "messages"
    memory_channel: str = "memory"
    model: str = "claude-sonnet-4-5"  # used by `summary`
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
    def compile(cls, cfg: MemoryConfig, ctx: NodeContext) -> NodeFn:
        if cfg.operation == "buffer":

            async def _buffer(state: dict[str, Any]) -> dict[str, Any]:
                latest = _last_text(state.get(cfg.input_channel))
                return {cfg.memory_channel: [latest]}

            return _buffer

        if ctx.model is None:
            raise ValueError("Memory summary requires a model client in NodeContext")
        model = ctx.model

        async def _summary(state: dict[str, Any]) -> dict[str, Any]:
            transcript = _transcript(state.get(cfg.input_channel))
            summary = await collect_text(
                model,
                model_id=cfg.model,
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
            f"    model = init_chat_model({cfg.model!r}, temperature={cfg.temperature})",
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
