"""Glue between the API and the agent engine: build a run context for a graph, and a
process-wide checkpointer for conversational memory in the playground."""

from __future__ import annotations

from calypr_dsl import GraphSpec
from calypr_nodes import NodeContext
from langgraph.checkpoint.memory import InMemorySaver

# Process-wide in-memory checkpointer so a playground thread keeps history across turns.
# (Durable Postgres checkpointing is a later hardening step — CLAUDE-PLAN.md §8.)
checkpointer = InMemorySaver()


def context_for(graph: GraphSpec) -> NodeContext:
    """An empty context: each LLM node resolves its *own* provider from its `model` id (so a
    Reflexion graph's Responder/Revisor use their configured models — not one model picked
    from a single Agent, which Reflexion doesn't even have)."""
    return NodeContext()
