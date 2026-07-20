"""Walk generated LangGraph Python back into a `GraphSpec` (topology + entry).

The forward generator (`calypr_codegen.generate_python`) emits a small, closed grammar. This
walker inverts exactly that grammar and nothing more:

    build_graph():
        graph = StateGraph(State)
        graph.add_node("<id>", node_<id>)                 # one per node
        graph.add_edge(START, "<entry>")                  # entry point
        graph.add_conditional_edges("<id>", route_<id>, {"<cond>": "<target>", ...})   # Router
        graph.add_conditional_edges("<id>", tools_condition, {"tools": "<t>", END: <done>})  # ReAct
        graph.add_edge("<src>", "<tgt>")                  # plain edge
        graph.add_edge("<id>", END)                        # terminal (output) — implicit in spec
        return graph.compile()

`START`/`END` are sentinels, not nodes: `add_edge(START, x)` becomes `entry`, and any edge into
`END` is dropped (the spec leaves END implicit). Router path-maps carry the branch condition in
their **keys**; `tools_condition` maps do not (they reconstruct to plain agent↔tool edges), so the
router function name (`route_*` vs `tools_condition`) is the discriminator.

Node *types* are not recoverable from the call graph alone. Each node function is offered to the
registered node types' `parse()` recognisers (the inverse of their `codegen()`, living beside it
in `packages/nodes`) in priority order; the first to claim the shape sets the node's type +
config. Any function no recogniser matches degrades to a `code` (Custom Code) node carrying its
source verbatim. The walker never raises on the generated surface: unrecognised statements and
recogniser errors become warnings, not failures.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field

from calypr_dsl import SCHEMA_VERSION, EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_nodes import NodeParseContext, get_node, has_node

_GRAPH_METHODS = {"add_node", "add_edge", "add_conditional_edges"}

# The order recognisers are tried in. A node function is offered to each type's `parse()`
# until one claims it; the first match wins, so more-specific shapes come first. `router`
# precedes `agent` because an LLM router also calls `init_chat_model` — it's disambiguated by
# its companion `route_*` function, which `router.parse()` keys on. Types absent here (or with
# no recogniser) never match and their nodes degrade to a `code` node — the same graceful
# fallback the parser had before any recogniser existed.
_RECOGNITION_ORDER = (
    "input",
    "output",
    "router",
    "agent",
    "tool",
    "retriever",
    "responder",
    "revisor",
    "evaluator",
    "memory",
    "image",
    "tts",
    "upload",
)

# Inverse of codegen's `_PYTYPE`: a generated Python annotation maps back to a canonical DSL
# type. The forward map is many-to-one (both "string"/"str" -> str), so we pick one canonical
# name per Python type; round-trip equivalence is defined modulo that (see the package README).
_DSL_TYPE: dict[str, str] = {
    "str": "string",
    "list": "list",
    "dict": "dict",
    "float": "number",
    "int": "integer",
    "bool": "boolean",
    "Any": "object",
}

_TRAILER_PREFIX = "# calypr:"
_TRAILER_NOQA = "# noqa: E501"


@dataclass
class ParseResult:
    """The outcome of parsing generated code.

    `spec` is always a valid `GraphSpec` (possibly with degraded nodes); `warnings` records
    anything the walker skipped; `degraded_nodes` lists node ids that fell back to a `code` node.
    """

    spec: GraphSpec
    warnings: list[str] = field(default_factory=list)
    degraded_nodes: list[str] = field(default_factory=list)


def _str_const(node: ast.expr | None) -> str | None:
    """Return the value of a string-literal expression, else None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_name(node: ast.expr | None, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _graph_call(stmt: ast.stmt) -> tuple[str, ast.Call] | None:
    """If `stmt` is `graph.<method>(...)` for a known builder method, return (method, call)."""
    value = stmt.value if isinstance(stmt, ast.Expr) else None
    if not isinstance(value, ast.Call):
        return None
    func = value.func
    if (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id == "graph"
        and func.attr in _GRAPH_METHODS
    ):
        return func.attr, value
    return None


def _channel(ann_assign: ast.AnnAssign, warnings: list[str]) -> StateChannel | None:
    """Recover one `StateChannel` from a `key: annotation` line of the `State` TypedDict.

    Inverts codegen's `_state_class`: `Annotated[list, add_messages]` -> the `messages` append
    channel; `Annotated[T, operator.add]` -> an append channel of type T; a plain annotation ->
    a `last` channel. Unknown annotations degrade to a `last`/`object` channel with a warning.
    """
    if not isinstance(ann_assign.target, ast.Name):
        return None
    key = ann_assign.target.id
    ann = ann_assign.annotation

    # Annotated[<inner>, <reducer-marker>]
    if isinstance(ann, ast.Subscript) and _is_name(ann.value, "Annotated"):
        args = ann.slice.elts if isinstance(ann.slice, ast.Tuple) else []
        inner = args[0] if args else None
        marker = args[1] if len(args) > 1 else None
        # `add_messages` (a Name) marks the canonical messages channel.
        if _is_name(marker, "add_messages"):
            return StateChannel(key=key, type="messages", reducer=Reducer.append)
        # `operator.add` (an Attribute) marks a generic append channel.
        pytype = inner.id if isinstance(inner, ast.Name) else "Any"
        return StateChannel(
            key=key, type=_DSL_TYPE.get(pytype, "object"), reducer=Reducer.append
        )

    if isinstance(ann, ast.Name):
        return StateChannel(key=key, type=_DSL_TYPE.get(ann.id, "object"), reducer=Reducer.last)

    warnings.append(f"state channel {key!r} has an unrecognised annotation — kept as object/last")
    return StateChannel(key=key, type="object", reducer=Reducer.last)


def _parse_state(tree: ast.Module, warnings: list[str]) -> list[StateChannel]:
    """Walk `class State(TypedDict, ...)` back into its channels (empty if absent)."""
    cls = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "State"), None
    )
    if cls is None:
        return []
    channels: list[StateChannel] = []
    for item in cls.body:
        if isinstance(item, ast.AnnAssign):
            ch = _channel(item, warnings)
            if ch is not None:
                channels.append(ch)
    return channels


def _parse_trailer(code: str, warnings: list[str]) -> dict | None:
    """Recover the `# calypr: {...}` metadata line (layout/identity), if present and well-formed."""
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped.startswith(_TRAILER_PREFIX):
            continue
        body = stripped[len(_TRAILER_PREFIX):].strip()
        if body.endswith(_TRAILER_NOQA):
            body = body[: -len(_TRAILER_NOQA)].strip()
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            warnings.append("found a # calypr: trailer but its JSON was malformed — ignored")
            return None
    return None


def _docstring_name(tree: ast.Module) -> str | None:
    """Recover the graph name from the module docstring `"<name> — generated by Calypr. ..."`."""
    doc = ast.get_docstring(tree)
    if doc and " — generated by Calypr" in doc:
        return doc.split(" — generated by Calypr", 1)[0].strip()
    return None


def parse_python(code: str) -> ParseResult:
    """Parse generated LangGraph Python into a `GraphSpec` (topology + entry).

    Robust by contract: syntactically-broken input or a missing `build_graph()` yields an empty
    spec plus a warning rather than raising.
    """
    warnings: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return ParseResult(
            spec=GraphSpec(id="parsed", name="Parsed Graph"),
            warnings=[f"could not parse source (syntax error: {exc.msg})"],
        )

    functions: dict[str, ast.FunctionDef] = {
        n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)
    }
    # Every top-level symbol → its defining statement (a function *or* an assignment such as
    # `node_x = ToolNode([...])`). Recognisers use this to resolve the name `add_node` points
    # at and to find companion defs (a `route_*` function, a `knowledge = ...` helper).
    top_defs: dict[str, ast.stmt] = dict(functions)
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    top_defs[tgt.id] = stmt

    build = functions.get("build_graph")
    if build is None:
        warnings.append("no build_graph() found — cannot recover topology")
        return ParseResult(spec=GraphSpec(id="parsed", name="Parsed Graph"), warnings=warnings)

    node_ids: list[str] = []
    node_fn: dict[str, str] = {}
    edges: list[EdgeSpec] = []
    entry: str | None = None

    def add_edge(source: str, target: str, condition: str | None = None) -> None:
        edges.append(
            EdgeSpec(id=f"e{len(edges)}", source=source, target=target, condition=condition)
        )

    for stmt in build.body:
        call = _graph_call(stmt)
        if call is None:
            continue  # `graph = StateGraph(State)`, `return graph.compile()`, comments, etc.
        method, node = call
        args = node.args

        if method == "add_node":
            node_id = _str_const(args[0]) if args else None
            if node_id is None:
                warnings.append("add_node with a non-literal id — skipped")
                continue
            node_ids.append(node_id)
            if len(args) > 1 and isinstance(args[1], ast.Name):
                node_fn[node_id] = args[1].id

        elif method == "add_edge":
            src, tgt = (args[0] if args else None), (args[1] if len(args) > 1 else None)
            if _is_name(src, "START"):
                entry = _str_const(tgt)
            elif _is_name(tgt, "END"):
                continue  # terminal edge; END is implicit in the spec
            else:
                s, t = _str_const(src), _str_const(tgt)
                if s is not None and t is not None:
                    add_edge(s, t)
                else:
                    warnings.append("add_edge with non-literal endpoints — skipped")

        elif method == "add_conditional_edges":
            source = _str_const(args[0]) if args else None
            router = args[1] if len(args) > 1 else None
            mapping = args[2] if len(args) > 2 else None
            if source is None or not isinstance(mapping, ast.Dict):
                warnings.append("add_conditional_edges with unexpected shape — skipped")
                continue
            is_router = isinstance(router, ast.Name) and router.id.startswith("route_")
            for key, val in zip(mapping.keys, mapping.values, strict=True):
                target = _str_const(val)
                if target is None:
                    continue  # e.g. `END: END` — no real target
                # Router keys are branch conditions; tools_condition maps are plain edges.
                condition = _str_const(key) if is_router else None
                add_edge(source, target, condition)

    # The `# calypr: {...}` trailer carries what code can't express (layout + identity). Absent
    # or malformed, parsing still succeeds: positions stay None and the canvas auto-layout applies.
    trailer = _parse_trailer(code, warnings)
    layout = (trailer or {}).get("layout", {})

    # Each node is offered to the recognisers in priority order; the first to claim it sets its
    # type + config. Any node no recogniser matches degrades to a `code` node with its source
    # preserved verbatim — the parser never rejects the generated surface.
    degraded: list[str] = []
    nodes: list[NodeSpec] = []
    for node_id in node_ids:
        ref = node_fn.get(node_id, "")
        defn = top_defs.get(ref)
        pctx = NodeParseContext(
            ref_name=ref,
            func=defn if isinstance(defn, ast.FunctionDef) else None,
            assign=defn if isinstance(defn, ast.Assign) else None,
            module=tree,
            source=code,
            defs=top_defs,
        )

        pos = layout.get(node_id)
        position = {"x": pos["x"], "y": pos["y"]} if isinstance(pos, dict) and "x" in pos else None

        node_type = "code"
        config: dict = {}
        for candidate in _RECOGNITION_ORDER:
            if not has_node(candidate):
                continue
            try:
                cfg = get_node(candidate).parse(pctx)
            except Exception as exc:  # a recogniser must never sink the whole parse
                warnings.append(f"{candidate}.parse() raised on {node_id!r}: {exc} — skipped")
                continue
            if cfg is not None:
                node_type, config = candidate, cfg.model_dump()
                break

        if node_type == "code":
            config = {"code": ast.get_source_segment(code, defn) or "" if defn else ""}
            degraded.append(node_id)
        nodes.append(NodeSpec(id=node_id, type=node_type, config=config, position=position))

    graph_meta = (trailer or {}).get("graph", {})
    spec = GraphSpec(
        schema_version=(trailer or {}).get("schema_version") or SCHEMA_VERSION,
        id=graph_meta.get("id") or "parsed",
        name=graph_meta.get("name") or _docstring_name(tree) or "Parsed Graph",
        description=graph_meta.get("description", ""),
        state=_parse_state(tree, warnings),
        nodes=nodes,
        edges=edges,
        entry=entry,
    )
    return ParseResult(spec=spec, warnings=warnings, degraded_nodes=degraded)
