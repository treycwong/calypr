"""Shared helper: run one streaming model call and collect the final text.

Used by capability nodes (Evaluator, Memory summary, Router classify) that make a single model
call. The Agent node keeps its own loop-aware version.

**These calls are internal and do not stream to the chat.** None of their callers writes to
`messages` — the Evaluator writes a score and a rationale, Memory writes a summary, the Router
picks a branch — so their text is scaffolding, not the answer. Streaming it appended the judge's
"SCORE: 5 …" straight onto the end of the reply the user was reading, with no separator and no
way to tell whose voice it was. `usage` is emitted regardless: the call costs money whether or
not anyone sees the words."""

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
    stream: bool = False,
) -> str:
    """`stream=True` only for a single-shot call whose text *is* the user-facing answer. Every
    current caller is internal, hence the default."""
    writer = safe_stream_writer()
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
            # Gated on its own, never by silencing the writer: metering must not depend on
            # whether the node's words happen to be shown.
            if stream:
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
