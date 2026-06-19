"""Execute compiled graphs — one-shot invoke and token-streaming run (CLAUDE-PLAN.md §8)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from calypr_compiler import compile_graph
from calypr_dsl import GraphSpec
from calypr_nodes import NodeContext
from langgraph.checkpoint.memory import InMemorySaver

from calypr_runtime.events import RunEvent


def _config(thread_id: str | None) -> dict:
    return {"configurable": {"thread_id": thread_id or str(uuid4())}}


async def run(
    spec: GraphSpec,
    ctx: NodeContext,
    user_input: str,
    *,
    thread_id: str | None = None,
    checkpointer: Any = None,
) -> dict[str, Any]:
    """Compile + run to completion; return the final state."""
    compiled = compile_graph(spec, ctx, checkpointer=checkpointer or InMemorySaver())
    return await compiled.ainvoke({"input": user_input}, _config(thread_id))


async def run_stream(
    spec: GraphSpec,
    ctx: NodeContext,
    user_input: str,
    *,
    thread_id: str | None = None,
    checkpointer: Any = None,
) -> AsyncIterator[RunEvent]:
    """Compile + run, yielding token/usage events as they arrive, then a final event."""
    compiled = compile_graph(spec, ctx, checkpointer=checkpointer or InMemorySaver())
    last_state: dict[str, Any] = {}
    async for mode, chunk in compiled.astream(
        {"input": user_input}, _config(thread_id), stream_mode=["custom", "values"]
    ):
        if mode == "custom":
            kind = chunk.get("type")
            if kind == "token":
                yield RunEvent(type="token", text=chunk.get("text", ""))
            elif kind == "usage":
                yield RunEvent(type="usage", state=chunk)
        elif mode == "values":
            last_state = chunk
    yield RunEvent(type="final", output=last_state.get("output", ""), state=last_state)
