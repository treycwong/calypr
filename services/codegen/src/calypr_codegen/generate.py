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

from calypr_dsl import SCHEMA_VERSION, GraphSpec, Reducer, StateChannel
from calypr_nodes import CodegenContext, get_node, graph_channels, has_node

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
    "asyncio",
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


def _metadata_trailer(graph: GraphSpec) -> str:
    """A single-line `# calypr: {...}` comment carrying what the code itself can't express —
    canvas layout, the graph's identity, and its human name/description. The reverse parser
    (`calypr_roundtrip`) restores these; if the user deletes the line, parsing still succeeds and
    the canvas auto-layout applies. Emitted *after* ruff formatting (a machine data line ruff
    would otherwise flag E501) and marked `noqa` so a later `ruff` run leaves it intact.
    """
    layout = {
        node.id: {"x": node.position["x"], "y": node.position["y"]}
        for node in graph.nodes
        if node.position and "x" in node.position and "y" in node.position
    }
    meta = {
        "schema_version": graph.schema_version or SCHEMA_VERSION,
        "graph": {"id": graph.id, "name": graph.name, "description": graph.description},
        "layout": layout,
    }
    return f"# calypr: {json.dumps(meta, separators=(',', ':'))}  # noqa: E501"


def _mcp_ordinals(graph: GraphSpec) -> dict[str, int]:
    """MCP Tool node id → its 0-based position among the graph's MCP nodes.

    Each MCP node emits a module-level client and tool list; without a per-node ordinal a
    two-server graph would emit `_mcp_client`/`mcp_tools` twice and the second would clobber the
    first, leaving both Tool nodes bound to the same server."""
    return {
        n.id: i
        for i, n in enumerate(
            n
            for n in graph.nodes
            if n.type == "tool" and n.config.get("provider") == "mcp"
        )
    }


def _tool_refs_by_node(graph: GraphSpec) -> dict[str, list[str]]:
    """Tool node id → the variable name(s) its tools live under in the generated module."""
    if not has_node("tool"):
        return {}
    tool_cls = get_node("tool")
    ordinals = _mcp_ordinals(graph)
    return {
        n.id: tool_cls.code_refs(
            tool_cls.config_model.model_validate(n.config), ordinals.get(n.id, 0)
        )
        for n in graph.nodes
        if n.type == "tool"
    }


def _tool_refs(graph: GraphSpec, by_node: dict[str, list[str]]) -> dict[str, list[str]]:
    """LLM node id → tool variable names to bind (resolved from edges to Tool nodes)."""
    refs: dict[str, list[str]] = {}
    for e in graph.edges:
        if e.target in by_node:
            refs.setdefault(e.source, []).extend(by_node[e.target])
    return refs


def _owner_map_src(name: str, targets: dict[str, list[str]]) -> str:
    """A module-level `{tool name: owning node id}` map, built from the tool objects themselves.

    An MCP server's tool names are only known once it has been contacted, so ownership can't be
    written out statically — it is derived at import time from the same lists the nodes bind."""
    entries = []
    for node_id, refs in targets.items():
        for ref in refs:
            src = ref[1:] if ref.startswith("*") else f"[{ref}]"
            entries.append(f"    **{{t.name: {node_id!r} for t in {src}}},")
    return f"{name} = {{\n" + "\n".join(entries) + "\n}"


def _tool_router_src(fn: str, owners: str, done: str) -> str:
    """A generated router that fans a turn's tool calls out to the Tool nodes that own them.

    The single-Tool-node case keeps LangGraph's stock `tools_condition`; this is only emitted
    when an agent is wired to several, where `tools_condition`'s one branch cannot express
    "this call goes to the GitHub node, that one to Notion"."""
    return (
        f"def {fn}(state: State):\n"
        f'    """Route each tool call to the Tool node that owns it (several may run)."""\n'
        '    messages = state.get("messages") or []\n'
        "    last = messages[-1] if messages else None\n"
        '    calls = getattr(last, "tool_calls", None)\n'
        "    if not calls:\n"
        f"        return {done!r}\n"
        "    # dedupe but keep order, so the branch taken is stable for a given turn\n"
        "    targets = list(\n"
        f'        dict.fromkeys(o for c in calls if (o := {owners}.get(c["name"])))\n'
        "    )\n"
        f"    return targets or {done!r}"
    )


def generate_python(graph: GraphSpec) -> str:
    """Render a complete, formatted Python module for `graph`."""
    fn_for: dict[str, str] = {}
    functions: list[str] = []
    imports: set[str] = {
        "from __future__ import annotations",
        "from langgraph.graph import END, START, StateGraph",
    }

    refs_by_tool_node = _tool_refs_by_node(graph)
    tool_refs = _tool_refs(graph, refs_by_tool_node)
    tool_node_ids = {n.id for n in graph.nodes if n.type == "tool"}
    mcp_ordinals = _mcp_ordinals(graph)

    routing_ids: set[str] = set()
    for node in graph.nodes:
        fn = _fn_name(node.id)
        fn_for[node.id] = fn
        node_cls = get_node(node.type)
        cfg = node_cls.config_model.model_validate(node.config)
        cg_ctx = CodegenContext(
            tool_refs=tool_refs.get(node.id, []),
            mcp_ordinal=mcp_ordinals.get(node.id, 0),
        )
        fragment = node_cls.codegen(cfg, fn, cg_ctx)
        functions.append(fragment.function.rstrip("\n"))
        imports.update(fragment.imports)
        if fragment.routing:
            routing_ids.add(node.id)

    # Owned channels (e.g. a loop counter) must appear in the generated State even if the
    # client's spec omitted them — same augmentation the compiler applies.
    state_src, state_imports = _state_class(graph_channels(graph.nodes, graph.state))
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
        tool_tgts = [e.target for e in out if e.target in tool_node_ids]
        done_tgt = next((e.target for e in out if e.target not in tool_node_ids), None)
        done_expr = f'"{done_tgt}"' if done_tgt else "END"
        if len(tool_tgts) < 2:
            imports.add("from langgraph.prebuilt import tools_condition")
            build.append(
                f'    graph.add_conditional_edges("{node.id}", tools_condition, '
                f'{{"tools": "{tool_tgts[0] if tool_tgts else None}", END: {done_expr}}})'
            )
            continue
        # Several Tool nodes on one agent: `tools_condition` has a single `tools` branch and so
        # can only ever reach one of them, while the agent binds all of their tools. Emit a
        # router that resolves each call to its owning node — the codegen mirror of
        # `AgentNode.routing`'s `tool_owners` fan-out.
        owners = f"_TOOL_OWNERS_{fn_for[node.id]}".upper()
        route_fn = f"route_{fn_for[node.id]}"
        done_key = done_tgt or "__end__"
        functions.append(
            _owner_map_src(owners, {t: refs_by_tool_node[t] for t in tool_tgts})
        )
        functions.append(_tool_router_src(route_fn, owners, done_key))
        mapping = ", ".join(f'"{t}": "{t}"' for t in tool_tgts)
        done_map = f'"{done_key}": {done_expr}'
        build.append(
            f'    graph.add_conditional_edges("{node.id}", {route_fn}, '
            f"{{{mapping}, {done_map}}})"
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
    # Append the metadata trailer after formatting: it's a single machine-data line ruff would
    # otherwise reflow/flag. Two blank lines precede it — ruff's canonical spacing after a
    # top-level function — so the result is already `ruff format`-stable (idempotent).
    return _ruff_format(module + "\n") + "\n\n" + _metadata_trailer(graph) + "\n"
