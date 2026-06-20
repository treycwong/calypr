"""Glue between the API and the agent engine: build a run context for a graph, and a
process-wide checkpointer for conversational memory in the playground."""

from __future__ import annotations

from calypr_dsl import GraphSpec
from calypr_model import model_for
from calypr_nodes import NodeContext
from langgraph.checkpoint.memory import InMemorySaver

# Process-wide in-memory checkpointer so a playground thread keeps history across turns.
# (Durable Postgres checkpointing is a later hardening step — CLAUDE-PLAN.md §8.)
checkpointer = InMemorySaver()


def context_for(graph: GraphSpec) -> NodeContext:
    """Pick the provider from the graph's (first) Agent node and build a NodeContext."""
    model_id = "fake"
    for node in graph.nodes:
        if node.type == "agent":
            model_id = str(node.config.get("model", "fake"))
            break
    return NodeContext(model=model_for(model_id))
