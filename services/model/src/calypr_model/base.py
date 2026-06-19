"""The ModelClient protocol — the single seam over LLM providers (CLAUDE-PLAN.md §10)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from calypr_model.events import StreamEvent
from calypr_model.messages import Msg


@runtime_checkable
class ModelClient(Protocol):
    """A thin, provider-agnostic chat interface.

    Tool-calling and streaming are first-class (the Agent loop needs them). Routing,
    failover, caching, and metering are intentionally out of scope for the MVP — a
    consumer meters by reacting to the `Usage` event.
    """

    def stream(
        self,
        *,
        model: str,
        messages: list[Msg],
        system: str = "",
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncIterator[StreamEvent]: ...
