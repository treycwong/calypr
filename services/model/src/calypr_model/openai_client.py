"""OpenAI adapter for the ModelClient protocol (streaming + tool calling).

Uses Chat Completions with streaming; tool-call argument fragments are accumulated
across chunks and parsed once complete. Exercised by the optional live test."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from calypr_model.events import Done, StreamEvent, TextDelta, ToolCall, Usage
from calypr_model.messages import Msg, Role


def _to_openai(messages: list[Msg], system: str) -> list[dict]:
    out: list[dict] = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        if m.role == Role.system:
            out.append({"role": "system", "content": m.content})
        elif m.role == Role.user:
            out.append({"role": "user", "content": m.content})
        elif m.role == Role.assistant:
            msg: dict = {"role": "assistant", "content": m.content or None}
            if m.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.args)},
                    }
                    for tc in m.tool_calls
                ]
            out.append(msg)
        elif m.role == Role.tool:
            out.append(
                {"role": "tool", "tool_call_id": m.tool_call_id, "content": m.content}
            )
    return out


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Map the unified tool schema {name, description, input_schema} to OpenAI tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get(
                    "input_schema",
                    t.get("parameters", {"type": "object", "properties": {}}),
                ),
            },
        }
        for t in tools
    ]


class OpenAIModelClient:
    """Reads OPENAI_API_KEY from the environment unless a key is passed.

    `base_url` points the OpenAI-compatible client at an alternate endpoint (Moonshot,
    DeepSeek). When None, the client talks to OpenAI as before — default behavior is
    unchanged.
    """

    def __init__(
        self, api_key: str | None = None, base_url: str | None = None
    ) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            base_url=base_url,
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
            "messages": _to_openai(messages, system),
            "temperature": temperature,
            "max_completion_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            kwargs["tools"] = _to_openai_tools(tools)

        parts: list[str] = []
        acc: dict[int, dict] = {}
        usage = None

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if chunk.usage is not None:
                usage = chunk.usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                parts.append(delta.content)
                yield TextDelta(text=delta.content)
            for tc in delta.tool_calls or []:
                slot = acc.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments

        tool_calls: list[ToolCall] = []
        for slot in acc.values():
            try:
                args = json.loads(slot["args"]) if slot["args"] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(id=slot["id"], name=slot["name"], args=args))

        for tc in tool_calls:
            yield tc
        if usage is not None:
            yield Usage(
                input_tokens=usage.prompt_tokens, output_tokens=usage.completion_tokens
            )
        yield Done(text="".join(parts), tool_calls=tool_calls)
