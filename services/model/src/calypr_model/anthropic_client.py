"""Anthropic adapter for the ModelClient protocol (streaming + tool use).

Exercised by the optional live test; the gate test uses FakeModelClient. Built against
the raw streaming events (stable across SDK versions) plus get_final_message()."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from calypr_model.events import Done, StreamEvent, TextDelta, ToolCall, Usage
from calypr_model.messages import Msg, Role


def _to_anthropic(messages: list[Msg]) -> list[dict]:
    out: list[dict] = []
    for m in messages:
        if m.role == Role.user:
            out.append({"role": "user", "content": m.content})
        elif m.role == Role.assistant:
            blocks: list[dict] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                blocks.append(
                    {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.args}
                )
            out.append({"role": "assistant", "content": blocks or m.content})
        elif m.role == Role.tool:
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": m.content,
                        }
                    ],
                }
            )
    return out


class AnthropicModelClient:
    """Reads ANTHROPIC_API_KEY from the environment unless a key is passed."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )

    async def stream(
        self,
        *,
        model: str,
        messages: list[Msg],
        system: str = "",
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[StreamEvent]:
        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": _to_anthropic(messages),
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        parts: list[str] = []
        async with self._client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_delta" and (
                    getattr(event.delta, "type", None) == "text_delta"
                ):
                    parts.append(event.delta.text)
                    yield TextDelta(text=event.delta.text)
            final = await stream.get_final_message()

        tool_calls = [
            ToolCall(id=b.id, name=b.name, args=dict(b.input))
            for b in final.content
            if getattr(b, "type", None) == "tool_use"
        ]
        for tc in tool_calls:
            yield tc
        if final.usage is not None:
            yield Usage(
                input_tokens=final.usage.input_tokens,
                output_tokens=final.usage.output_tokens,
            )
        yield Done(text="".join(parts), tool_calls=tool_calls)
