"""Shared helper: run one streaming model call and collect the final text.

Used by capability nodes (Evaluator, Memory summary) that make a single model call. The
Agent node keeps its own loop-aware version. Tokens stream to the playground via the same
custom stream writer the Agent uses."""

from __future__ import annotations

from calypr_model import Done, Msg, TextDelta, Usage

from calypr_nodes._convert import safe_stream_writer


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
                    "input_tokens": ev.input_tokens,
                    "output_tokens": ev.output_tokens,
                }
            )
        elif isinstance(ev, Done):
            text = ev.text
    return text
