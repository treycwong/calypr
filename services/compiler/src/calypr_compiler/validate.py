"""Structured graph validation (CLAUDE-PLAN.md §8).

Returns issues mapped back onto node/edge ids so the canvas can highlight them. The
compiler refuses to build if any error-severity issue is present.
"""

from __future__ import annotations

from typing import Literal

from calypr_dsl import GraphSpec
from calypr_nodes import get_node, has_node
from pydantic import BaseModel, ValidationError


class Issue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None


def validate_graph(spec: GraphSpec) -> list[Issue]:
    issues: list[Issue] = []
    id_set = {n.id for n in spec.nodes}

    # Duplicate node ids.
    seen: set[str] = set()
    for n in spec.nodes:
        if n.id in seen:
            issues.append(
                Issue(
                    severity="error",
                    code="duplicate_node_id",
                    message=f"Duplicate node id {n.id!r}",
                    node_id=n.id,
                )
            )
        seen.add(n.id)

    # Known node types + valid config.
    for n in spec.nodes:
        if not has_node(n.type):
            issues.append(
                Issue(
                    severity="error",
                    code="unknown_node_type",
                    message=f"Unknown node type {n.type!r}",
                    node_id=n.id,
                )
            )
            continue
        try:
            get_node(n.type).config_model.model_validate(n.config)
        except ValidationError as exc:
            first = exc.errors()[0] if exc.errors() else {}
            issues.append(
                Issue(
                    severity="error",
                    code="invalid_config",
                    message=f"Invalid config for {n.id!r}: {first.get('msg', exc)}",
                    node_id=n.id,
                )
            )

    # Entry.
    if not spec.entry:
        issues.append(
            Issue(severity="error", code="no_entry", message="Graph has no entry node")
        )
    elif spec.entry not in id_set:
        issues.append(
            Issue(
                severity="error",
                code="bad_entry",
                message=f"Entry {spec.entry!r} is not a node",
                node_id=spec.entry,
            )
        )

    # Edges reference existing nodes.
    out_edges: dict[str, list[str]] = {}
    for e in spec.edges:
        out_edges.setdefault(e.source, []).append(e.target)
        for endpoint in (e.source, e.target):
            if endpoint not in id_set:
                issues.append(
                    Issue(
                        severity="error",
                        code="dangling_edge",
                        message=f"Edge {e.id!r} references unknown node {endpoint!r}",
                        edge_id=e.id,
                    )
                )

    # At least one Output node.
    if not any(n.type == "output" for n in spec.nodes):
        issues.append(
            Issue(
                severity="error", code="no_output", message="Graph has no Output node"
            )
        )

    # Non-output nodes must have an outgoing edge (no dead-ends).
    for n in spec.nodes:
        if n.type != "output" and not out_edges.get(n.id):
            issues.append(
                Issue(
                    severity="error",
                    code="dead_end",
                    message=f"Node {n.id!r} has no outgoing edge",
                    node_id=n.id,
                )
            )

    # Infinite-loop guard: a cycle reachable via only *unconditional* edges can never exit,
    # so the graph would run to the recursion limit (a wall of repeated calls). Legitimate
    # loops — a ReAct agent↔Tool loop, a Router — always traverse a conditional edge to get
    # back, so they don't appear in this unconditional-edge subgraph; the runtime
    # recursion_limit backstops those. Report the first such cycle found.
    plain_adj: dict[str, list[str]] = {}
    for e in spec.edges:
        if not e.condition and e.source in id_set and e.target in id_set:
            plain_adj.setdefault(e.source, []).append(e.target)

    color: dict[str, int] = {}  # 0 = visiting (on stack), 1 = done

    def _find_cycle(start: str) -> list[str] | None:
        # Iterative DFS tracking the current path so a back-edge yields the cycle nodes.
        stack: list[tuple[str, int]] = [(start, 0)]
        path: list[str] = []
        while stack:
            node, i = stack[-1]
            if i == 0:
                color[node] = 0
                path.append(node)
            neighbours = plain_adj.get(node, [])
            if i < len(neighbours):
                stack[-1] = (node, i + 1)
                nxt = neighbours[i]
                if color.get(nxt) == 0:  # back-edge into the current path → cycle
                    return path[path.index(nxt):]
                if nxt not in color:
                    stack.append((nxt, 0))
            else:
                color[node] = 1
                path.pop()
                stack.pop()
        return None

    for n in spec.nodes:
        if n.id not in color:
            cycle = _find_cycle(n.id)
            if cycle:
                loop = " → ".join(cycle + [cycle[0]])
                issues.append(
                    Issue(
                        severity="error",
                        code="cyclic_graph",
                        message=(
                            f"Nodes form a loop with no exit ({loop}). A run would repeat "
                            "until it errors. Remove the back-edge, or route through a "
                            "Router/Tool step that can break out of the loop."
                        ),
                        node_id=cycle[0],
                    )
                )
                break

    # Router branch coverage: a router branches by edge `condition`, so every branch (and
    # the default) must have a matching conditional out-edge. This keeps both the compiled
    # graph and the generated code from ever routing to a missing branch.
    for n in spec.nodes:
        if n.type != "router" or not has_node("router"):
            continue
        try:
            cfg = get_node("router").config_model.model_validate(n.config)
        except ValidationError:
            continue
        wired = {e.condition for e in spec.edges if e.source == n.id and e.condition}
        if not wired:
            issues.append(
                Issue(
                    severity="error",
                    code="router_no_branches",
                    message=f"Router {n.id!r} has no conditional out-edges",
                    node_id=n.id,
                )
            )
            continue
        expected = {b.name for b in cfg.branches}
        if cfg.default:
            expected.add(cfg.default)
        for name in sorted(expected - wired):
            issues.append(
                Issue(
                    severity="error",
                    code="router_branch_unwired",
                    message=f"Router {n.id!r} branch {name!r} has no matching edge",
                    node_id=n.id,
                )
            )

    # ReAct: an agent wired to a Tool node branches like `tools_condition`, so it needs a
    # 'tools' edge (→ the Tool node) and a 'respond' edge (→ Output) — otherwise it would
    # route to a missing branch when it stops (or never stops) calling tools.
    tool_node_ids = {n.id for n in spec.nodes if n.type == "tool"}
    for n in spec.nodes:
        if n.type != "agent":
            continue
        out = [e for e in spec.edges if e.source == n.id]
        if not any(e.target in tool_node_ids for e in out):
            continue
        conds = {e.condition for e in out if e.condition}
        if "tools" not in conds or "respond" not in conds:
            issues.append(
                Issue(
                    severity="error",
                    code="react_branches_unwired",
                    message=(
                        f"Agent {n.id!r} uses tools but its branches aren't wired "
                        "('tools' → the Tool node, 'respond' → Output). Start from the "
                        "ReAct template."
                    ),
                    node_id=n.id,
                )
            )

    # Reachability from entry.
    if spec.entry in id_set:
        reachable: set[str] = set()
        stack = [spec.entry]
        while stack:
            cur = stack.pop()
            if cur in reachable:
                continue
            reachable.add(cur)
            stack.extend(out_edges.get(cur, []))
        for n in spec.nodes:
            if n.id not in reachable:
                issues.append(
                    Issue(
                        severity="warning",
                        code="unreachable",
                        message=f"Node {n.id!r} is unreachable from entry",
                        node_id=n.id,
                    )
                )

    # Nodes writing channels the state never declares (likely a mistake).
    declared = {c.key for c in spec.state}
    for n in spec.nodes:
        if not has_node(n.type):
            continue
        try:
            cfg = get_node(n.type).config_model.model_validate(n.config)
        except ValidationError:
            continue
        for channel in get_node(n.type).writes(cfg):
            if channel not in declared:
                issues.append(
                    Issue(
                        severity="warning",
                        code="undeclared_channel",
                        message=f"Node {n.id!r} writes undeclared channel {channel!r}",
                        node_id=n.id,
                    )
                )

    return issues
