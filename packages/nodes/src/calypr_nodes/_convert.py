"""Bridges between LangGraph's message state (langchain_core) and the model layer's
neutral messages, plus small helpers (prompt templating, safe stream writer)."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from calypr_model import Msg, Role, ToolCallRequest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

_TEMPLATE = re.compile(r"{{\s*state\.([A-Za-z_]\w*)\s*}}")


def text_of(message: BaseMessage) -> str:
    """Flatten a message's content (str or content blocks) to plain text."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def lc_to_msgs(messages: list[BaseMessage]) -> list[Msg]:
    """Convert LangGraph message state into provider-neutral `Msg`s."""
    out: list[Msg] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            out.append(Msg(role=Role.user, content=text_of(m)))
        elif isinstance(m, SystemMessage):
            out.append(Msg(role=Role.system, content=text_of(m)))
        elif isinstance(m, AIMessage):
            tool_calls = [
                ToolCallRequest(id=tc["id"], name=tc["name"], args=tc.get("args", {}))
                for tc in (m.tool_calls or [])
            ]
            out.append(
                Msg(role=Role.assistant, content=text_of(m), tool_calls=tool_calls)
            )
        elif isinstance(m, ToolMessage):
            out.append(
                Msg(role=Role.tool, content=text_of(m), tool_call_id=m.tool_call_id)
            )
    return out


def render_template(template: str, state: dict[str, Any]) -> str:
    """Interpolate `{{ state.key }}` references against the current state."""
    return _TEMPLATE.sub(lambda m: str(state.get(m.group(1), "")), template)


def safe_stream_writer() -> Callable[[Any], None]:
    """Return LangGraph's custom stream writer, or a no-op outside a run context."""
    try:
        from langgraph.config import get_stream_writer

        return get_stream_writer()
    except Exception:
        return lambda _payload: None
