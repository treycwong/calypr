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

Recognisers key on the **stable docstring + structural shape** the generator emits. Where a node's
whole config is recoverable from structure alone (`input`, `output`), the recogniser falls back to
that shape, so rewriting the docstring costs nothing. For the rest — an Agent especially — the
docstring is the only record of *which* variant it is, so a rewritten docstring degrades that node
to a Code node **on purpose**: guessing the variant would silently change behaviour, while
degrading preserves the user's code verbatim.

## Edit survival (measured)

The round-trip is only worth anything if it survives a human editing the code first. That is
measured, not assumed: `tests/mutations.py` applies realistic hand-edits across the whole corpus
and `tests/test_mutations.py` judges every result, in two tiers.

**Robustness — holds for 100% of (graph, edit) pairs.** `parse_python` never raises; topology
(node ids, edges, entry) and state channels come back exactly as the edit implies; and no node is
ever **misclassified** — a node is either its true type or a degraded `code` node, never some
*other* concrete type. A bad edit can cost you one node's structure; it can never silently corrupt
the graph.

**Clean absorption — measured, gated at ≥95%.** For edits inside the generated idiom, the parser
recovers them with no degradation at all and the change reflected in config. Edits that leave the
idiom degrade *exactly* the node they touched.

| Edit | Class | Expectation |
|---|---|---|
| change a system prompt | absorb | new prompt in config |
| change a temperature | absorb | new value in config |
| rename a channel | absorb | channel renamed in config + State |
| add an inline `# comment` | absorb | ignored entirely |
| delete the `# calypr:` trailer | absorb | parses; layout falls back to auto-layout |
| reflow formatting (collapse wrapped strings, squeeze blank lines) | absorb | no-op for recovery |
| rewrite a docstring | absorb *or* degrade | `input`/`output` survive structurally; others degrade to a Code node |
| add / remove an edge | topology | edge set follows |
| rename a node id | topology | id follows everywhere |
| insert a hand-written node | degrade | that node becomes a Code node; the rest is untouched |

Current measurement — **robustness 100%** over 378 (graph, edit) pairs, **clean absorption 100%**
over 307 in-idiom pairs. The suite prints the per-edit table on failure, so a regression shows up
as a number rather than a vibe:

```
uv run pytest services/roundtrip/tests/test_mutations.py -k survival_rates -s
```

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
