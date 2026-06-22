"""GraphSpec → LangGraph StateGraph (CLAUDE-PLAN.md §8).

Validate first (refuse on any error), build the state schema, compile each node via the
registry, wire control-flow edges, and route Output nodes to END.
"""

from __future__ import annotations

from dataclasses import replace

from calypr_dsl import GraphSpec
from calypr_nodes import NodeContext, get_node, has_node
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from calypr_compiler.state import build_state_type
from calypr_compiler.validate import Issue, validate_graph


def _tools_bound_to(spec: GraphSpec) -> dict[str, list[dict]]:
    """Map each LLM node id → the tool bind-schemas of the Tool nodes it points to.

    Edge-driven binding: an Agent/Responder/Revisor wired to a Tool node both *binds* that
    tool (here) and *executes* it (the Tool node + the conditional loop)."""
    if not has_node("tool"):
        return {}
    tool_cls = get_node("tool")
    schemas_by_tool: dict[str, list[dict]] = {
        n.id: tool_cls.bind_schemas(tool_cls.config_model.model_validate(n.config))
        for n in spec.nodes
        if n.type == "tool"
    }
    bound: dict[str, list[dict]] = {}
    for e in spec.edges:
        if e.target in schemas_by_tool:
            bound.setdefault(e.source, []).extend(schemas_by_tool[e.target])
    return bound


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

    bound_tools = _tools_bound_to(spec)

    compiled: dict[str, tuple] = {}
    for node in spec.nodes:
        node_cls = get_node(node.type)
        cfg = node_cls.config_model.model_validate(node.config)
        # Inject the node's bound tools (if any) so it binds + routes like the generated code.
        node_ctx = replace(ctx, tools=bound_tools[node.id]) if node.id in bound_tools else ctx
        compiled[node.id] = (node_cls, cfg, node_ctx)
        builder.add_node(node.id, node_cls.compile(cfg, node_ctx))

    builder.add_edge(START, spec.entry)

    # Routing nodes (If-Else, or an agent with tools) decide a branch name; wire their
    # labelled out-edges as conditional edges and skip them in the plain pass below.
    routing_sources: set[str] = set()
    for node in spec.nodes:
        node_cls, cfg, node_ctx = compiled[node.id]
        path_fn = node_cls.routing(cfg, node_ctx)
        if path_fn is None:
            continue
        routing_sources.add(node.id)
        path_map = {
            e.condition: e.target
            for e in spec.edges
            if e.source == node.id and e.condition
        }
        builder.add_conditional_edges(node.id, path_fn, path_map)

    for edge in spec.edges:
        if edge.source in routing_sources:
            continue  # handled by add_conditional_edges
        builder.add_edge(edge.source, edge.target)
    for node in spec.nodes:
        if node.type == "output":
            builder.add_edge(node.id, END)

    return builder.compile(checkpointer=checkpointer)
