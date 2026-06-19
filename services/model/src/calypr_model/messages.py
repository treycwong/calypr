"""Provider-neutral chat messages. The nodes layer converts to/from LangGraph's
message state; this module stays free of langchain so the model layer is swappable."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Role(StrEnum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


@dataclass
class ToolCallRequest:
    """A tool invocation the assistant asked for."""

    id: str
    name: str
    args: dict


@dataclass
class Msg:
    role: Role
    content: str = ""
    # assistant turns may carry tool calls; tool turns carry the id they answer.
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tool_call_id: str | None = None
