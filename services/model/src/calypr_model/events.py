"""Streaming events a ModelClient yields, in arrival order, ending with `Done`."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextDelta:
    """An incremental chunk of assistant text."""

    text: str


@dataclass
class ToolCall:
    """A fully-formed tool call the assistant requested."""

    id: str
    name: str
    args: dict


@dataclass
class Usage:
    """Token usage for the turn — the hook a metering layer reacts to (deferred)."""

    input_tokens: int
    output_tokens: int


@dataclass
class Done:
    """Terminal event: the assembled assistant turn."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


StreamEvent = TextDelta | ToolCall | Usage | Done
