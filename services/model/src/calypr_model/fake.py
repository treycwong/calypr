"""A deterministic, key-free ModelClient for tests and local demos."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from calypr_model.events import Done, StreamEvent, TextDelta, ToolCall, Usage
from calypr_model.messages import Msg, Role

_CHUNK = 6


class FakeModelClient:
    """Echoes the last user message (or a fixed `reply`), streamed in small chunks.

    Optionally emits a scripted list of tool calls — useful for exercising the Agent
    tool loop without a real provider.
    """

    def __init__(
        self,
        reply: str | None = None,
        tool_calls: Sequence[ToolCall] | None = None,
    ) -> None:
        self._reply = reply
        self._tool_calls = list(tool_calls or [])

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
        last_user = next(
            (m.content for m in reversed(messages) if m.role == Role.user), ""
        )
        text = self._reply if self._reply is not None else f"Echo: {last_user}"
        for i in range(0, len(text), _CHUNK):
            yield TextDelta(text=text[i : i + _CHUNK])
        for tc in self._tool_calls:
            yield tc
        yield Usage(
            input_tokens=len(last_user.split()), output_tokens=len(text.split())
        )
        yield Done(text=text, tool_calls=list(self._tool_calls))
