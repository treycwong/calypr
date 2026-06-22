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
