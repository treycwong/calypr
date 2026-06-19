"""GraphSpec → LangGraph StateGraph (CLAUDE-PLAN.md §8).

Validate first (refuse on any error), build the state schema, compile each node via the
registry, wire control-flow edges, and route Output nodes to END.
"""

from __future__ import annotations

from calypr_dsl import GraphSpec
from calypr_nodes import NodeContext, get_node
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from calypr_compiler.state import build_state_type
from calypr_compiler.validate import Issue, validate_graph


class CompileError(Exception):
    """Raised when a GraphSpec fails validation. Carries node-mapped issues."""

    def __init__(self, issues: list[Issue]) -> None:
        self.issues = issues
        super().__init__(
            f"{len(issues)} compile error(s): "
            + "; ".join(f"[{i.code}] {i.message}" for i in issues)
        )


def compile_graph(
    spec: GraphSpec,
    ctx: NodeContext,
    *,
    checkpointer=None,
) -> CompiledStateGraph:
    """Compile a GraphSpec into an executable LangGraph graph."""
    errors = [i for i in validate_graph(spec) if i.severity == "error"]
    if errors:
        raise CompileError(errors)

    state_type = build_state_type(spec.state)
    builder = StateGraph(state_type)

    for node in spec.nodes:
        node_cls = get_node(node.type)
        cfg = node_cls.config_model.model_validate(node.config)
        builder.add_node(node.id, node_cls.compile(cfg, ctx))

    builder.add_edge(START, spec.entry)
    for edge in spec.edges:
        # Phase 1: control-flow edges are unconditional. Router/conditional edges and
        # handoffs arrive with the Router (Phase 2) and multi-agent (Phase 5) work.
        builder.add_edge(edge.source, edge.target)
    for node in spec.nodes:
        if node.type == "output":
            builder.add_edge(node.id, END)

    return builder.compile(checkpointer=checkpointer)
