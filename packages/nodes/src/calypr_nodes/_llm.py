"""Shared helper: run one streaming model call and collect the final text.

Used by capability nodes (Evaluator, Memory summary) that make a single model call. The
Agent node keeps its own loop-aware version. Tokens stream to the playground via the same
custom stream writer the Agent uses."""

from __future__ import annotations

from calypr_model import Done, Msg, TextDelta, ToolCall, Usage
from langchain_core.messages import AIMessage

from calypr_nodes._context import current_node_id
from calypr_nodes._convert import safe_stream_writer


async def actor_message(
    model,
    *,
    model_id: str,
    system: str,
    messages: list[Msg],
    tools: list[dict],
    temperature: float = 0.0,
    max_tokens: int = 1024,
    stream: bool = True,
) -> AIMessage:
    """One streaming model call that may request tools; returns an AIMessage carrying the
    text + any tool calls (so a wired Tool node can act). Used by Responder/Revisor."""
    writer = safe_stream_writer() if stream else (lambda _payload: None)
    text = ""
    calls: list[ToolCall] = []
    async for ev in model.stream(
        model=model_id,
        system=system,
        messages=messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        if isinstance(ev, TextDelta):
            writer({"type": "token", "text": ev.text})
        elif isinstance(ev, ToolCall):
            calls.append(ev)
        elif isinstance(ev, Usage):
            writer(
                {
                    "type": "usage",
                    "node_id": current_node_id.get(None),
                    "model": model_id,
                    "input_tokens": ev.input_tokens,
                    "output_tokens": ev.output_tokens,
                }
            )
        elif isinstance(ev, Done):
            text = ev.text
            calls = ev.tool_calls or calls
    return AIMessage(
        content=text,
        tool_calls=[{"id": c.id, "name": c.name, "args": c.args} for c in calls],
    )


async def collect_text(
    model,
    *,
    model_id: str,
    system: str,
    messages: list[Msg],
    temperature: float = 0.0,
    max_tokens: int = 1024,
    stream: bool = True,
) -> str:
    writer = safe_stream_writer() if stream else (lambda _payload: None)
    text = ""
    async for ev in model.stream(
        model=model_id,
        system=system,
        messages=messages,
        tools=[],
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        if isinstance(ev, TextDelta):
            writer({"type": "token", "text": ev.text})
        elif isinstance(ev, Usage):
            writer(
                {
                    "type": "usage",
                    "node_id": current_node_id.get(None),
                    "model": model_id,
                    "input_tokens": ev.input_tokens,
                    "output_tokens": ev.output_tokens,
                }
            )
        elif isinstance(ev, Done):
            text = ev.text
    return text
