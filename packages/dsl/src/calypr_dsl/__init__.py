"""Calypr DSL — the GraphSpec contract (Pydantic source of truth).

TypeScript types are generated from these models; a CI drift check keeps the canvas
and compiler in lockstep (CLAUDE-PLAN.md §7).
"""

from calypr_dsl.spec import (
    SCHEMA_VERSION,
    EdgeSpec,
    GraphSpec,
    NodeSpec,
    Reducer,
    StateChannel,
)

__version__ = "0.0.0"

__all__ = [
    "SCHEMA_VERSION",
    "Reducer",
    "StateChannel",
    "NodeSpec",
    "EdgeSpec",
    "GraphSpec",
]
