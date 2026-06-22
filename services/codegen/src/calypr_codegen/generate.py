"""Generate a standalone, idiomatic LangGraph module from a GraphSpec.

The output is meant to read like a senior engineer wrote it: a `State` TypedDict from the
channels, one function per node (from each node's `codegen()`), and a `build_graph()` that
wires the StateGraph. It is formatted with `ruff` and depends only on langgraph/langchain —
not on Calypr — so the user truly owns it (CLAUDE-PLAN realignment §Phase 3).
"""

from __future__ import annotations

import json
import re
import subprocess

from calypr_dsl import GraphSpec, Reducer, StateChannel
from calypr_nodes import CodegenContext, get_node, has_node

_PYTYPE: dict[str, str] = {
    "string": "str",
    "str": "str",
    "list": "list",
    "messages": "list",
    "dict": "dict",
    "object": "dict",
    "number": "float",
    "integer": "int",
    "boolean": "bool",
    "bool": "bool",
}

_STDLIB_ROOTS = {
    "__future__",
    "typing",
    "operator",
    "os",
    "json",
    "re",
    "collections",
    "textwrap",
    "dataclasses",
}


def _fn_name(node_id: str) -> str:
    name = re.sub(r"\W", "_", node_id)
    return f"node_{name}"


def _state_class(channels: list[StateChannel]) -> tuple[str, set[str]]:
    imports = {"from typing import TypedDict"}
    lines = ["class State(TypedDict, total=False):"]
    if not channels:
        lines.append("    pass")
    for ch in channels:
        pytype = _PYTYPE.get(ch.type, "Any")
        if pytype == "Any":
            imports.add("from typing import Any")
        if ch.reducer == Reducer.append:
            imports.add("from typing import Annotated")
            if ch.key == "messages":
                imports.add("from langgraph.graph.message import add_messages")
                ann = "Annotated[list, add_messages]"
            else:
                imports.add("import operator")
                ann = f"Annotated[{pytype}, operator.add]"
        else:
            ann = pytype
        lines.append(f"    {ch.key}: {ann}")
    return "\n".join(lines), imports


def _render_imports(lines: set[str]) -> str:
    """Merge `from X import ...` per module, sort names, group future/stdlib/third-party."""
    from_imports: dict[str, set[str]] = {}
    plain: set[str] = set()
    for raw in lines:
        line = raw.strip()
        if line.startswith("from "):
            module, _, names = line[5:].partition(" import ")
            for name in names.split(","):
                from_imports.setdefault(module.strip(), set()).add(name.strip())
        elif line.startswith("import "):
            plain.add(line[7:].strip())

    # Each section emits straight `import x` first, then `from x import ...`, each sorted
    # by module name — matching ruff/isort's default (force-sort-within-sections off).
    groups: dict[str, dict[str, list[str]]] = {
        k: {"plain": [], "from": []} for k in ("future", "std", "third")
    }

    def bucket(module: str) -> str:
        if module == "__future__":
            return "future"
        return "std" if module.split(".")[0] in _STDLIB_ROOTS else "third"

    for module in plain:
        groups[bucket(module)]["plain"].append(f"import {module}")
    for module, names in from_imports.items():
        groups[bucket(module)]["from"].append(
            f"from {module} import {', '.join(sorted(names))}"
        )

    blocks: list[str] = []
    for k in ("future", "std", "third"):
        section = sorted(groups[k]["plain"]) + sorted(
            groups[k]["from"], key=lambda s: s.split()[1]
        )
        if section:
            blocks.append("\n".join(section))
    return "\n\n".join(blocks)


def _ruff_format(code: str) -> str:
    try:
        result = subprocess.run(
            ["ruff", "format", "-"],
            input=code,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except Exception:
        return code


def _tool_refs(graph: GraphSpec) -> dict[str, list[str]]:
    """LLM node id → tool variable names to bind (resolved from edges to Tool nodes)."""
    if not has_node("tool"):
        return {}
    tool_cls = get_node("tool")
    tool_nodes = {n.id: n for n in graph.nodes if n.type == "tool"}
    refs: dict[str, list[str]] = {}
    for e in graph.edges:
        if e.target in tool_nodes:
            cfg = tool_cls.config_model.model_validate(tool_nodes[e.target].config)
            refs.setdefault(e.source, []).extend(tool_cls.code_refs(cfg))
    return refs


def generate_python(graph: GraphSpec) -> str:
    """Render a complete, formatted Python module for `graph`."""
    fn_for: dict[str, str] = {}
    functions: list[str] = []
    imports: set[str] = {
        "from __future__ import annotations",
        "from langgraph.graph import END, START, StateGraph",
    }

    tool_refs = _tool_refs(graph)
    tool_node_ids = {n.id for n in graph.nodes if n.type == "tool"}

    routing_ids: set[str] = set()
    for node in graph.nodes:
        fn = _fn_name(node.id)
        fn_for[node.id] = fn
        node_cls = get_node(node.type)
        cfg = node_cls.config_model.model_validate(node.config)
        cg_ctx = CodegenContext(tool_refs=tool_refs.get(node.id, []))
        fragment = node_cls.codegen(cfg, fn, cg_ctx)
        functions.append(fragment.function.rstrip("\n"))
        imports.update(fragment.imports)
        if fragment.routing:
            routing_ids.add(node.id)

    state_src, state_imports = _state_class(graph.state)
    imports.update(state_imports)

    build = ["def build_graph():", '    """Build and compile the agent graph."""']
    build.append("    graph = StateGraph(State)")
    for node in graph.nodes:
        build.append(f'    graph.add_node("{node.id}", {fn_for[node.id]})')
    if graph.entry:
        build.append(f'    graph.add_edge(START, "{graph.entry}")')
    # Conditional edges for routing nodes (If-Else): branch name -> target.
    for node in graph.nodes:
        if node.id not in routing_ids:
            continue
        path_map = {
            e.condition: e.target
            for e in graph.edges
            if e.source == node.id and e.condition
        }
        mapping = ", ".join(
            f"{json.dumps(k)}: {json.dumps(v)}" for k, v in path_map.items()
        )
        build.append(
            f'    graph.add_conditional_edges("{node.id}", '
            f"route_{fn_for[node.id]}, {{{mapping}}})"
        )
    # ReAct: an agent wired to a Tool node binds it and branches with `tools_condition`
    # (the canonical loop) — route to the tool node, else finish at its respond target.
    tool_routers: set[str] = set()
    for node in graph.nodes:
        if node.type != "agent" or node.id not in tool_refs:
            continue
        tool_routers.add(node.id)
        out = [e for e in graph.edges if e.source == node.id]
        tools_tgt = next((e.target for e in out if e.target in tool_node_ids), None)
        done_tgt = next((e.target for e in out if e.target not in tool_node_ids), None)
        done_expr = f'"{done_tgt}"' if done_tgt else "END"
        imports.add("from langgraph.prebuilt import tools_condition")
        build.append(
            f'    graph.add_conditional_edges("{node.id}", tools_condition, '
            f'{{"tools": "{tools_tgt}", END: {done_expr}}})'
        )
    for edge in graph.edges:
        if edge.source in routing_ids or edge.source in tool_routers:
            continue  # handled by add_conditional_edges
        build.append(f'    graph.add_edge("{edge.source}", "{edge.target}")')
    for node in graph.nodes:
        if node.type == "output":
            build.append(f'    graph.add_edge("{node.id}", END)')
    build.append("    return graph.compile()")

    module = "\n\n".join(
        [
            f'"""{graph.name} — generated by Calypr. Owns no Calypr dependency."""',
            _render_imports(imports),
            state_src,
            *functions,
            "\n".join(build),
        ]
    )
    return _ruff_format(module + "\n")
