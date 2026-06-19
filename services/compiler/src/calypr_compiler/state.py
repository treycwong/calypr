"""Build a LangGraph state schema from the DSL's declared channels.

Each channel becomes a typed field; an `append` reducer maps to `add_messages` for the
canonical messages channel and to list concatenation otherwise. Last-write channels are
plain fields (LangGraph's default overwrite behaviour).
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from calypr_dsl import Reducer, StateChannel
from langgraph.graph.message import add_messages

_PYTYPE: dict[str, type] = {
    "string": str,
    "str": str,
    "list": list,
    "messages": list,
    "dict": dict,
    "object": dict,
    "number": float,
    "integer": int,
    "boolean": bool,
    "bool": bool,
}


def _annotation(channel: StateChannel) -> Any:
    pytype: Any = _PYTYPE.get(channel.type, Any)
    if channel.reducer == Reducer.append:
        reducer = add_messages if channel.key == "messages" else operator.add
        return Annotated[pytype, reducer]
    return pytype


def build_state_type(channels: list[StateChannel]) -> type:
    """Return a TypedDict (with reducer annotations) for use as a StateGraph schema."""
    annotations = {channel.key: _annotation(channel) for channel in channels}
    return TypedDict("CalyprState", annotations, total=False)
