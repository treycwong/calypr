"""Realistic, human-style edits to generated code — the Week-7 edit-survival corpus.

Each operator is a deterministic `str -> str` transform over a generated module, paired with an
`Expect` describing how the *parsed* result should differ from the un-mutated baseline. They edit
at the line/string level rather than rewriting the AST, because that is how a person actually
edits a file they just exported.

Operators return `None` when they don't apply to a given graph (e.g. no Agent node to retune), so
the suite can run every operator over every template without special-casing.

Three outcome classes:

- **absorb** — the edit stays inside the generated idiom; the parser should recover it cleanly,
  keeping every node's type (the config simply reflects the change).
- **topology** — the edit changes the graph shape; nodes/edges should follow, types unchanged.
- **degrade** — the edit leaves the idiom; the touched node must fall back to a `code` node with
  its source preserved, and nothing else may be affected.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from calypr_dsl import GraphSpec

NEW_PROMPT = "You are a laconic pirate. Answer in one sentence."
NEW_TEMPERATURE = 0.123
RENAMED_CHANNEL = "result"
RENAMED_NODE = "renamed_node"
HANDWRITTEN_NODE = "handwritten"


@dataclass
class Expect:
    """How the parsed spec should differ from the un-mutated baseline parse."""

    degraded: set[str] = field(default_factory=set)  # ids that must fall back to a `code` node
    added_nodes: set[str] = field(default_factory=set)
    added_edges: set[tuple[str, str]] = field(default_factory=set)
    removed_edges: set[tuple[str, str]] = field(default_factory=set)
    renames: dict[str, str] = field(default_factory=dict)  # old node id -> new node id
    state_may_change: bool = False
    # (node_id, config key, expected value) — proves the edit actually landed in the spec.
    config_expect: tuple[str, str, object] | None = None
    # Overrides the operator's default outcome class when a single operator can land in more
    # than one (a docstring rewrite is absorbed by a structurally-recoverable node, but degrades
    # any other). None → use `KIND[operator]`.
    kind: str | None = None


# An operator: (code, spec) -> (mutated code, expectation), or None when not applicable.
Operator = Callable[[str, GraphSpec], "tuple[str, Expect] | None"]
# A node-targeted operator additionally takes the node id it should edit.
NodeOperator = Callable[[str, GraphSpec, str], "tuple[str, Expect] | None"]


def _first_node(spec: GraphSpec, node_type: str) -> str | None:
    return next((n.id for n in spec.nodes if n.type == node_type), None)


def _fn_name(node_id: str) -> str:
    """Mirror of codegen's `_fn_name` — the function a node id compiles to."""
    return f"node_{re.sub(r'\\W', '_', node_id)}"


def _block(lines: list[str], fn_name: str) -> tuple[int, int] | None:
    """The [start, end) line range of a top-level `def <fn_name>(...)` block."""
    start = next(
        (i for i, ln in enumerate(lines) if ln.startswith(f"def {fn_name}(")), None
    )
    if start is None:
        return None
    for i in range(start + 1, len(lines)):
        if lines[i] and not lines[i][0].isspace():  # next top-level statement
            return start, i
    return start, len(lines)


def _replace_assignment(lines: list[str], lo: int, hi: int, name: str, value: str) -> bool:
    """Replace a `name = <literal>` assignment (single-line or parenthesised) inside [lo, hi)."""
    for i in range(lo, hi):
        stripped = lines[i].lstrip()
        if not stripped.startswith(f"{name} = "):
            continue
        indent = lines[i][: len(lines[i]) - len(stripped)]
        end = i + 1
        if stripped.rstrip().endswith("("):  # parenthesised implicit concatenation
            while end < hi and lines[end].strip() != ")":
                end += 1
            end += 1
        lines[i:end] = [f"{indent}{name} = {json.dumps(value)}"]
        return True
    return False


def change_prompt(code: str, spec: GraphSpec) -> tuple[str, Expect] | None:
    """Rewrite an Agent's system prompt — the single most likely hand-edit."""
    node_id = _first_node(spec, "agent")
    if node_id is None:
        return None
    lines = code.splitlines()
    span = _block(lines, _fn_name(node_id))
    if span is None or not _replace_assignment(lines, *span, "system", NEW_PROMPT):
        return None
    return "\n".join(lines) + "\n", Expect(
        config_expect=(node_id, "system_prompt", NEW_PROMPT)
    )


def change_temperature(code: str, spec: GraphSpec) -> tuple[str, Expect] | None:
    """Retune an Agent's temperature."""
    node_id = _first_node(spec, "agent")
    if node_id is None:
        return None
    lines = code.splitlines()
    span = _block(lines, _fn_name(node_id))
    if span is None:
        return None
    lo, hi = span
    for i in range(lo, hi):
        if "temperature=" in lines[i]:
            lines[i] = re.sub(r"temperature=[0-9.]+", f"temperature={NEW_TEMPERATURE}", lines[i])
            return "\n".join(lines) + "\n", Expect(
                config_expect=(node_id, "temperature", NEW_TEMPERATURE)
            )
    return None


def rename_channel(code: str, spec: GraphSpec) -> tuple[str, Expect] | None:
    """Rename the Output node's result channel — touches both the State class and the return."""
    node_id = _first_node(spec, "output")
    if node_id is None:
        return None
    node = next(n for n in spec.nodes if n.id == node_id)
    old = node.config.get("output_channel", "output")
    if old == RENAMED_CHANNEL or f'"{old}"' not in code:
        return None
    if any(n.id == old for n in spec.nodes):
        return None  # the channel name doubles as a node id — a blind rename would hit both
    renamed = code.replace(f'"{old}"', f'"{RENAMED_CHANNEL}"')
    # ...and the State annotation, which is a bare identifier rather than a string.
    renamed = re.sub(rf"^    {re.escape(old)}: ", f"    {RENAMED_CHANNEL}: ", renamed, flags=re.M)
    if renamed == code:
        return None
    return renamed, Expect(
        state_may_change=True,
        config_expect=(node_id, "output_channel", RENAMED_CHANNEL),
    )


def add_inline_comment(code: str, spec: GraphSpec, node_id: str) -> tuple[str, Expect] | None:
    """Drop a `# note to self` line into a node body — must be entirely ignored."""
    lines = code.splitlines()
    span = _block(lines, _fn_name(node_id))
    if span is None:
        return None
    lo, hi = span
    for i in range(lo + 1, hi):  # after the def line (and its docstring)
        if lines[i].strip() and not lines[i].lstrip().startswith('"""'):
            lines.insert(i, "    # tweaked this by hand")
            return "\n".join(lines) + "\n", Expect()
    return None


def add_edge(code: str, spec: GraphSpec) -> tuple[str, Expect] | None:
    """Wire up an extra edge by hand between two existing nodes."""
    if len(spec.nodes) < 2:
        return None
    existing = {(e.source, e.target) for e in spec.edges}
    pair = next(
        (
            (a.id, b.id)
            for a in spec.nodes
            for b in spec.nodes
            if a.id != b.id and (a.id, b.id) not in existing
        ),
        None,
    )
    if pair is None:
        return None
    lines = code.splitlines()
    anchor = next((i for i, ln in enumerate(lines) if "    return graph.compile()" in ln), None)
    if anchor is None:
        return None
    lines.insert(anchor, f'    graph.add_edge("{pair[0]}", "{pair[1]}")')
    return "\n".join(lines) + "\n", Expect(added_edges={pair})


def remove_edge(code: str, spec: GraphSpec) -> tuple[str, Expect] | None:
    """Delete a plain edge line (never the START/END sentinels)."""
    lines = code.splitlines()
    pattern = re.compile(r'^    graph\.add_edge\("([^"]+)", "([^"]+)"\)$')
    for i, ln in enumerate(lines):
        m = pattern.match(ln)
        if m:
            del lines[i]
            return "\n".join(lines) + "\n", Expect(removed_edges={(m.group(1), m.group(2))})
    return None


def rename_node_id(code: str, spec: GraphSpec) -> tuple[str, Expect] | None:
    """Rename a node id everywhere it appears (add_node, edges, trailer layout)."""
    if not spec.nodes:
        return None
    old = spec.nodes[0].id
    if f'"{old}"' not in code:
        return None
    if any(c.key == old for c in spec.state):
        return None  # the node id doubles as a channel name — a blind rename would hit both
    return code.replace(f'"{old}"', f'"{RENAMED_NODE}"'), Expect(renames={old: RENAMED_NODE})


def delete_trailer(code: str, spec: GraphSpec) -> tuple[str, Expect] | None:
    """Strip the `# calypr:` metadata line — layout is lost, everything else must survive."""
    lines = [ln for ln in code.splitlines() if not ln.strip().startswith("# calypr:")]
    if len(lines) == len(code.splitlines()):
        return None
    return "\n".join(lines) + "\n", Expect()


def deformat(code: str, spec: GraphSpec) -> tuple[str, Expect] | None:
    """Reflow the module the way another formatter (or an impatient human) would: collapse
    parenthesised implicit string concatenation onto one line and squeeze blank lines.

    Textually large, semantically identical — the parser works on the AST, so this must be a
    complete no-op for recovery. This is the independent-formatter stress without adding a
    formatter dependency to a deliberately ruff-only repo."""
    lines = code.splitlines()
    out: list[str] = []
    i = 0
    changed = False
    while i < len(lines):
        stripped = lines[i].lstrip()
        m = re.match(r"^(\w+) = \($", stripped)
        if m:
            indent = lines[i][: len(lines[i]) - len(stripped)]
            parts: list[str] = []
            j = i + 1
            while j < len(lines) and lines[j].strip() != ")":
                parts.append(lines[j].strip())
                j += 1
            joined = " ".join(parts)
            try:  # implicit concatenation is valid Python, so literal_eval folds it for us
                value = ast.literal_eval(joined)
            except (ValueError, SyntaxError):
                out.append(lines[i])
                i += 1
                continue
            if isinstance(value, str):
                out.append(f"{indent}{m.group(1)} = {json.dumps(value)}")
                i = j + 1
                changed = True
                continue
        out.append(lines[i])
        i += 1

    squeezed: list[str] = []
    for ln in out:  # collapse runs of blank lines
        if not ln.strip() and squeezed and not squeezed[-1].strip():
            changed = True
            continue
        squeezed.append(ln)
    if not changed:
        return None
    return "\n".join(squeezed) + "\n", Expect()


#: Node types whose whole config is recoverable from code *structure*, so their recognisers keep
#: working when the docstring is rewritten. Every other type keys on the docstring, and rewriting
#: it degrades that node to a Code node — deliberately: for an Agent the docstring is the only
#: record of *which* agent type it is, and guessing would silently change behaviour, whereas
#: degrading preserves the user's code verbatim.
STRUCTURALLY_RECOVERABLE = {"input", "output"}


def edit_docstring(code: str, spec: GraphSpec, node_id: str) -> tuple[str, Expect] | None:
    """Rewrite a node's docstring — a natural edit, and the main thing recognisers key on.

    Expectation depends on the node type: `input`/`output` survive via their structural
    fallback; everything else degrades to a Code node, isolated and never misclassified."""
    lines = code.splitlines()
    span = _block(lines, _fn_name(node_id))
    if span is None:
        return None
    lo, hi = span
    node_type = next((n.type for n in spec.nodes if n.id == node_id), "")
    survives = node_type in STRUCTURALLY_RECOVERABLE
    for i in range(lo + 1, hi):
        if lines[i].lstrip().startswith('"""'):
            lines[i] = '    """My own notes about this step."""'
            expect = (
                Expect(kind="absorb")
                if survives
                else Expect(degraded={node_id}, kind="degrade")
            )
            return "\n".join(lines) + "\n", expect
    return None


def insert_handwritten_node(code: str, spec: GraphSpec) -> tuple[str, Expect] | None:
    """Add a node the user wrote themselves — the canonical out-of-idiom edit."""
    if not spec.nodes:
        return None
    source = spec.nodes[0].id
    lines = code.splitlines()
    anchor = next((i for i, ln in enumerate(lines) if ln.startswith("def build_graph(")), None)
    ret = next((i for i, ln in enumerate(lines) if "    return graph.compile()" in ln), None)
    if anchor is None or ret is None:
        return None
    fn = [
        f"def {_fn_name(HANDWRITTEN_NODE)}(state: State) -> dict:",
        '    """Bespoke step I wrote myself."""',
        "    tally = len(state.get('messages') or [])",
        '    return {"tally": tally}',
        "",
        "",
    ]
    lines[anchor:anchor] = fn
    ret += len(fn)
    lines[ret:ret] = [
        f'    graph.add_node("{HANDWRITTEN_NODE}", {_fn_name(HANDWRITTEN_NODE)})',
        f'    graph.add_edge("{source}", "{HANDWRITTEN_NODE}")',
    ]
    return "\n".join(lines) + "\n", Expect(
        added_nodes={HANDWRITTEN_NODE},
        added_edges={(source, HANDWRITTEN_NODE)},
        degraded={HANDWRITTEN_NODE},
    )


# Graph-level operators: one mutation per graph.
GRAPH_LEVEL: dict[str, Operator] = {
    "change_prompt": change_prompt,
    "change_temperature": change_temperature,
    "rename_channel": rename_channel,
    "delete_trailer": delete_trailer,
    "deformat": deformat,
    "add_edge": add_edge,
    "remove_edge": remove_edge,
    "rename_node_id": rename_node_id,
    "insert_handwritten_node": insert_handwritten_node,
}

# Node-targeted operators: applied to *every* node in turn, so each node type's recogniser is
# actually stressed rather than only whichever node happens to be first.
PER_NODE: dict[str, NodeOperator] = {
    "add_inline_comment": add_inline_comment,
    "edit_docstring": edit_docstring,
}

KIND = {
    "change_prompt": "absorb",
    "change_temperature": "absorb",
    "rename_channel": "absorb",
    "delete_trailer": "absorb",
    "deformat": "absorb",
    "add_inline_comment": "absorb",
    "add_edge": "topology",
    "remove_edge": "topology",
    "rename_node_id": "topology",
    "edit_docstring": "degrade",
    "insert_handwritten_node": "degrade",
}


def iter_mutations(code: str, spec: GraphSpec) -> list[tuple[str, str, Expect]]:
    """Every applicable edit for one graph as `(label, mutated code, expectation)`.

    Node-targeted operators expand to one entry per node (labelled `op@node_id`), so a docstring
    rewrite is exercised against every recogniser rather than just the first node's."""
    out: list[tuple[str, str, Expect]] = []
    for name, op in GRAPH_LEVEL.items():
        applied = op(code, spec)
        if applied is not None:
            out.append((name, applied[0], applied[1]))
    for name, node_op in PER_NODE.items():
        for node in spec.nodes:
            applied = node_op(code, spec, node.id)
            if applied is not None:
                out.append((f"{name}@{node.id}", applied[0], applied[1]))
    return out


def base_name(label: str) -> str:
    """`edit_docstring@agent` -> `edit_docstring`."""
    return label.split("@", 1)[0]
