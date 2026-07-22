"""Glue between the API and the agent engine: build a run context for a graph, and a
process-wide checkpointer for conversational memory in the playground."""

from __future__ import annotations

import uuid

from calypr_dsl import GraphSpec
from calypr_nodes import NodeContext
from langgraph.checkpoint.memory import InMemorySaver

from calypr_api.provider_keys import resolve_model_keys

# Process-wide in-memory checkpointer so a playground thread keeps history across turns.
# (Durable Postgres checkpointing is a later hardening step — CLAUDE-PLAN.md §8.)
checkpointer = InMemorySaver()


def context_for(graph: GraphSpec, workspace_id: uuid.UUID | None = None) -> NodeContext:
    """Build the run context. Each LLM node still resolves its *own* provider from its `model`
    id (so a Reflexion graph's Responder/Revisor use their configured models). When a workspace
    is given, its BYO provider keys are resolved from the vault and carried on the context so
    the model factory runs on those (overriding the server env per provider); with no workspace
    or no keys, the server env is used exactly as before."""
    keys = resolve_model_keys(workspace_id) if workspace_id else {}
    return NodeContext(model_keys=keys or None)
