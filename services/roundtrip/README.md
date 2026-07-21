# calypr-roundtrip

Reverse round-trip for Calypr: parse generated LangGraph Python back into a `GraphSpec`.

`calypr-codegen` turns a `GraphSpec` (the visual canvas's versioned DSL) into a standalone,
idiomatic LangGraph module. This package inverts that:

```python
from calypr_roundtrip import parse_python

result = parse_python(code)   # -> ParseResult(spec, warnings, degraded_nodes)
result.spec                   # a GraphSpec you can load back onto the canvas
result.degraded_nodes         # ids of functions no recogniser matched (kept as Code nodes)
```

Together the two make the "no ceiling" promise real: **canvas → code → edit → canvas**. A user
can drop into the generated Python, change it, and bring it back to the visual graph.

## How it works

The generated surface is a **closed grammar**, not arbitrary Python, so the parser is a targeted
AST walker rather than a general Python analyser:

- **Topology + state** — `build_graph()` emits only `add_node` / `add_edge` /
  `add_conditional_edges` over string literals and `START`/`END`; the `State` TypedDict encodes
  each channel's reducer. A walker recovers nodes, edges, entry, conditional branches (including
  the ReAct `tools_condition` shape), and state channels mechanically.
- **Node type + config** — each node function is offered to the registered node types'
  `parse()` recognisers, in priority order, until one claims it. Every `parse()` lives *beside*
  that node's `codegen()` in `calypr_nodes`, so the forward and inverse can't silently drift — a
  registry-wide property test (below) enforces it.
- **Graceful degradation** — a function no recogniser matches becomes a **Code (Custom Code)**
  node with its source preserved verbatim, and its id is listed in `degraded_nodes`. The parser
  **never raises** on the generated surface; an unrecognised edit degrades one node, it does not
  reject the file.
- **The `# calypr:` trailer** — one JSON comment carries what code can't express (canvas layout,
  the graph's id/name/description). Delete it and parsing still succeeds: positions become
  `None` and the canvas auto-layout applies.

## The equivalence relation

Round-tripping is lossless **up to a documented equivalence** — the things the generated code
genuinely cannot express are regenerated deterministically rather than preserved:

- **Node type + config** round-trip as a **codegen fixed point**:
  `generate_python(parse_python(generate_python(spec)).spec) == generate_python(spec)`, byte for
  byte, for every shipped node type. Config fields the generator never emits — e.g. an Agent's
  `max_tokens`, a cosmetic `label`, a Tool's runtime `api_key` — come back as their defaults.
  That is lossless *for the round-trip* precisely because those fields don't change the code.
- **Topology** (node ids, edge source/target, entry) and **state channels**
  (`key`, `reducer`, Python type) round-trip exactly. The forward type map is many-to-one
  (`string`/`str` → `str`), so channel types compare up to that canonicalisation.
- **Edge ids** are regenerated (they carry no meaning beyond identity).
- **Edge conditions** round-trip for **Router** branches (emitted losslessly as
  `add_conditional_edges(..., route_*, {cond: target})`) but **not** for ReAct agent↔tool wiring:
  that goes through LangGraph's `tools_condition`, whose fixed `"tools"`/`END` keys discard the
  spec's condition labels. Dropping them is behaviourally lossless — re-applying the plain
  agent→tool / agent→done edges regenerates identical wiring.
- **Identity + layout** (`id`/`name`/`description`, node positions) round-trip via the
  `# calypr:` trailer; without it, the id falls back to `"parsed"`, the name is read from the
  module docstring, and positions are `None`.

Recognisers key on the **stable docstring + structural shape** the generator emits. Hardening the
recovery against a user who rewrites a docstring or reformats heavily is the edit-survival work
tracked separately (the mutation suite); this package targets the generated surface and realistic
edits within its idiom.

## Tests

`services/roundtrip/tests/test_roundtrip.py` runs over the golden builder + every shipped starter
template and asserts:

- `test_node_types_recovered` — no node degrades; no node is misclassified.
- `test_codegen_fixed_point` — the `generate ∘ parse ∘ generate` fixed point above.
- `test_every_registered_node_type_has_a_recogniser` — a new node type can't ship without a
  `parse()` inverse and round-trip coverage.
- topology / state / trailer round-trip and the graceful-degradation + malformed-input paths.

```
uv run pytest services/roundtrip/tests
```
