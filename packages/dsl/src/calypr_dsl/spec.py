"""The Calypr DSL — `GraphSpec` and friends.

This is the **single source of truth** for the canvas graph contract. TypeScript types
are generated from these models (see `codegen.py`), so the canvas (TS) and the
compiler (Python) can never drift — a CI drift check enforces it (CLAUDE-PLAN.md §7).

Phase 0 keeps `NodeSpec.config` open (`dict`). In Phase 1 it becomes a discriminated
union validated per node type by the node registry (CLAUDE-PLAN.md §5).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

#: Bump on any backwards-incompatible change to the spec shape.
SCHEMA_VERSION = "0.1.0"


class Reducer(StrEnum):
    """How concurrent/iterative writes to a state channel merge (LangGraph reducer)."""

    append = "append"  # list channels (e.g. `messages`)
    last = "last"  # scalar channels: last write wins


class StateChannel(BaseModel):
    """One typed variable in the shared graph state."""

    key: str
    type: str = "string"  # MVP: simple type tags; richer types in Phase 1
    reducer: Reducer = Reducer.last
    default: Any | None = None


class NodeSpec(BaseModel):
    """A vertex in the control-flow graph. `type` resolves to a node-registry entry."""

    id: str
    type: str  # registry id, e.g. "input" | "agent" | "output"
    config: dict[str, Any] = Field(default_factory=dict)
    # Canvas-only layout metadata; ignored by the compiler.
    position: dict[str, float] | None = None


class EdgeSpec(BaseModel):
    """A directed control-flow edge. `condition` is set on edges leaving a Router."""

    id: str
    source: str
    target: str
    condition: str | None = None


class GraphSpec(BaseModel):
    """A complete agent graph as drawn on the canvas."""

    schema_version: str = SCHEMA_VERSION
    id: str
    name: str
    description: str = ""
    state: list[StateChannel] = Field(default_factory=list)
    nodes: list[NodeSpec] = Field(default_factory=list)
    edges: list[EdgeSpec] = Field(default_factory=list)
    entry: str | None = None  # id of the Input/Trigger node


__all__ = [
    "SCHEMA_VERSION",
    "Reducer",
    "StateChannel",
    "NodeSpec",
    "EdgeSpec",
    "GraphSpec",
]


def ancestors(spec: GraphSpec) -> dict[str, frozenset[str]]:
    """Every node id reachable *backwards* from each node, following edges.

    Pure topology, so it lives in the DSL rather than in the compiler: the runtime and the code
    generator both need the same answer, and they do not depend on each other.

    Transitive rather than immediate — `Image → Agent → Video` should still let the Video block
    recognise the picture its own branch produced, and a one-hop parent map loses that the moment
    anything sits between the two. Cycles are fine: the walk is a visited-set traversal, so a
    Reflexion loop terminates.

    Used to disambiguate a fan-out. Blocks share state channels, so two Image blocks both append to
    `messages` and a Video block downstream of one of them cannot otherwise tell which picture is
    its own — before this, both branches silently used whichever image landed last.
    """
    parents: dict[str, list[str]] = {n.id: [] for n in spec.nodes}
    for edge in spec.edges:
        if edge.target in parents:
            parents[edge.target].append(edge.source)

    out: dict[str, frozenset[str]] = {}
    for node in spec.nodes:
        seen: set[str] = set()
        queue = list(parents.get(node.id, ()))
        while queue:
            current = queue.pop()
            if current in seen:
                continue
            seen.add(current)
            queue.extend(parents.get(current, ()))
        out[node.id] = frozenset(seen)
    return out
