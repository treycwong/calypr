# Calypr — Week 5: Reverse round-trip parser, topology + state (execution plan)

**Date:** 2026-07-13 · **Status:** PLAN · Tracks `MVP-EXECUTION-PLAN.md` Month 2 → Week 5
(the existential track: code → GraphSpec). Builds on shipped Month 1 (Weeks 1–4: analytics,
metering + durable checkpointer, share links, friendly errors — PRs #2–#13, all prod-verified).

## 0. Why this week exists

The "no-ceiling" promise is currently unkeepable: `services/codegen` generates Python from a
GraphSpec (forward), but nothing parses edited code back to a spec. A user who drops into code
cannot return to the canvas. Month 2 (Weeks 5–8) makes the thesis technically true; Week 5 lays
the foundation: a new `services/roundtrip` package that recovers **graph topology + State
channels** from generated code. Node-config recognizers (Week 6), edit-survival (Week 7), and
the `POST /parse` + "Apply to canvas" UI (Week 8) all sit on top of this.

**Month-1 gate caveat (standing kill condition):** the blind code-review panel has not run yet
(non-eng, tracked in `TODO.md`). If it lands **<70% would-merge**, this week — and as much of
Month 2 as needed — redirects to codegen quality in `services/codegen/generate.py` + per-node
`codegen()`. Honor the gate, no exceptions. Run/kick off the panel in parallel with this week.

## 1. Verified current state (code audit 2026-07-13)

- **No reverse parser exists.** Grep for `parse_python` / `ast.parse` → nothing. All existing
  "round-trip" tests are forward-only (generate → import → run → compare behavior; see
  `services/codegen/tests/test_codegen.py::test_router_branches_and_round_trips` and its
  `_import_generated` helper).
- **The generated surface is a closed grammar** (`services/codegen/src/calypr_codegen/generate.py`,
  `generate_python()` ~line 141). `build_graph()` emits only:
  - `graph = StateGraph(State)`
  - `graph.add_node("<node.id>", node_<sanitized_id>)` per node (`_fn_name`, line ~44)
  - entry: `graph.add_edge(START, "<graph.entry>")`
  - routers: `graph.add_conditional_edges("<id>", route_<fn>, {<condition>: <target>, …})`
  - **ReAct agents:** `graph.add_conditional_edges("<id>", tools_condition, {"tools": "<tool>",
    END: …})` — a third conditional shape the MVP plan didn't call out; the walker must
    recognize it (it maps back to plain agent↔tool edges, not router edges).
  - plain `graph.add_edge("<source>", "<target>")`; outputs `graph.add_edge("<id>", END)`;
    `return graph.compile()`.
- **State** is emitted by `_state_class()` (~line 49) as `class State(TypedDict, total=False)`:
  `Annotated[list, add_messages]` ↔ the `messages` append channel; `Annotated[<T>, operator.add]`
  ↔ `Reducer.append` on other keys; plain annotation ↔ `Reducer.last`. Type map is `_PYTYPE`
  (~line 18) — the walker inverts it.
- **No metadata trailer exists today.** The only non-code artifact is the module docstring.
  Layout (`NodeSpec.position`), graph `id`/`description`, and edge `id`s are **unrecoverable
  from code** — the trailer (this week) carries layout/labels; ids regenerate.
- **Test corpus:** `services/compiler/src/calypr_compiler/golden.py` (one builder,
  `input_agent_output`) + `templates.py` `STARTERS` = 9 `FRAMEWORKS` + 5 `TEMPLATES` (14 specs
  spanning input→agent→output up to Reflexion, RAG, routing, orchestrator–worker). Existing
  tests are parametrized fixtures (`services/compiler/tests/test_templates.py`); no Hypothesis
  in the repo — follow the parametrized pattern.
- **Package template:** `services/codegen` — hatchling `pyproject.toml`, uv workspace deps
  (`calypr-dsl`, `calypr-nodes`, `{ workspace = true }`), `src/` layout, sibling `tests/`.
  Registration = add the path to root `pyproject.toml` `[tool.uv.workspace].members` **and**
  `[tool.pytest.ini_options].testpaths`; CI (`.github/workflows/ci.yml`) runs one
  `uv run pytest` + `uvx ruff check .` and picks the new package up automatically.
- **GraphSpec** (`packages/dsl/src/calypr_dsl/spec.py`): `SCHEMA_VERSION = "0.1.0"`;
  `NodeSpec(id, type, config, position?)`, `EdgeSpec(id, source, target, condition?)`,
  `StateChannel(key, type, reducer, default?)`, `GraphSpec(schema_version, id, name,
  description, state, nodes, edges, entry?)`.

## 2. Architecture (decided in `MVP-EXECUTION-PLAN.md`; restated as the contract)

**Approach C (AST parse of the closed grammar) + a thin Approach-A anchor:**

- `parse_python(code: str) -> ParseResult(spec: GraphSpec, warnings: list[str],
  degraded_nodes: list[str])`.
- **Graceful degradation is the core contract:** any node function no recognizer matches
  becomes a `code` (Custom Code) node with its body preserved verbatim. The parser **never
  hard-fails** on the generated surface — an unrecognizable edit degrades one node, it does
  not reject the file. This is the "constrained surface, not a general Python parser" mandate
  in code form, and it's built *first* (Week 5 has no recognizers yet, so every node degrades —
  the fallback path is exercised from day one).
- **A-anchor:** one `# calypr: {"schema_version": …, "graph": {id,name,description},
  "layout": {node_id: {x,y}}, "labels": {…}}` trailer comment emitted by `generate.py`. If the
  user deletes it, parsing still succeeds; the existing left-to-right auto-layout applies.
- **Week 5 scope = topology + state only.** Node-type/config recovery (per-node `parse()`
  beside each `codegen()` in `packages/nodes`) is Week 6.

## 3. PR-1 — `services/roundtrip` package + topology walker (~2d)

**Goal:** nodes/edges/entry/conditions recovered from generated code for every shipped spec.

- **Scaffold** `services/roundtrip/` mirroring `services/codegen`: `pyproject.toml`
  (name `calypr-roundtrip`, deps `calypr-dsl` + `calypr-nodes`, workspace sources, hatchling),
  `src/calypr_roundtrip/{__init__.py, parse.py}`, `tests/`. Register in root
  `pyproject.toml` (`workspace.members` + `testpaths`).
- **`parse.py`** — `parse_python()` via stdlib `ast.parse`:
  - locate `def build_graph()`; walk its statements, recognizing exactly the emitted calls:
    `add_node` → `NodeSpec` (id from the string arg; type resolution deferred — see below);
    `add_edge(START, x)` → `entry`; `add_edge(a, b)` / `add_edge(x, END)` → `EdgeSpec`;
    `add_conditional_edges(id, route_fn, {…})` → one `EdgeSpec(condition=key)` per path-map
    entry; `add_conditional_edges(id, tools_condition, {…})` → the agent↔tool edge pair
    (ReAct wiring, not router edges).
  - non-matching statements inside `build_graph()` → a warning, never an exception.
  - every node function body is captured (via `ast.get_source_segment`) and, absent a Week-6
    recognizer, the node comes back as `type="code"` with the body in config and its id in
    `degraded_nodes` — the degradation path *is* the Week 5 placeholder mechanism.
- **Gates:** `uv run pytest` — parametrized over `golden.py` + all 14 `STARTERS`:
  `parse_python(generate_python(spec))` recovers identical node-id sets, edge
  (source, target, condition) sets, and entry. Full pytest + ruff green.

## 4. PR-2 — State walker + metadata trailer (~2d)

**Goal:** State channels round-trip; layout/name survive via the trailer; its deletion is safe.

- **State walker** (in `parse.py`): parse `class State(TypedDict, total=False)` annotations
  back to `StateChannel`s — `Annotated[list, add_messages]` ↔ `key="messages"`,
  `reducer=append`; `Annotated[T, operator.add]` ↔ `reducer=append`; plain ↔ `reducer=last`;
  inverse of `_PYTYPE` for the `type` field. Unknown annotations → `type="json"` + a warning.
- **Trailer emission** in `generate.py`: append the single `# calypr: {…}` JSON comment
  (schema_version, graph id/name/description, per-node `position`, labels). Verify it survives
  `_ruff_format` (it runs *inside* `generate_python`, so emit after formatting or confirm ruff
  preserves the trailing comment). Forward tests (`test_codegen.py`, `test_templates.py`)
  updated to tolerate/assert the trailer.
- **Trailer consumption** in `parse.py`: when present → restore layout/name/description/ids;
  when absent → parse succeeds, `position=None` everywhere (canvas auto-layout applies),
  regenerated graph id, warning noted.
- **Equivalence relation, documented** in `services/roundtrip/README.md` (seeds the Week-7 /
  Week-11 OSS content): spec ≍ parsed-spec means equal topology (node ids, edge
  source/target/condition sets, entry) + equal state channels; edge ids and — without the
  trailer — layout/graph-id/description are regenerated, by design.
- **Gates:** parametrized test over all `STARTERS`: full equivalence (topology + state +
  layout/name via trailer) holds; a trailer-stripped copy still parses with the documented
  degradation. Full pytest + ruff green.

## 5. Verification (end-to-end)

- `uv run pytest` (new `services/roundtrip/tests` + updated codegen/template tests) and
  `uvx ruff check .` — existing CI job covers both with no workflow edits.
- No deploy surface this week: pure Python package, nothing user-visible until Week 8's
  `POST /parse` + "Apply to canvas". Merging to `main` auto-deploys Railway/Vercel as usual
  but changes no runtime behavior (the trailer in generated code is the only visible diff —
  spot-check the Code tab in prod renders it sanely).

## 6. Rollout

1. **PR-1** (package + topology walker) → CI green → merge.
2. **PR-2** (state walker + trailer) → CI green → merge → prod smoke: open a template's Code
   tab on www.calypr.co, confirm the trailer renders and code still runs in the playground.

Week-5 "Done" (per `MVP-EXECUTION-PLAN.md`): **topology round-trips for every graph in
`golden.py` + all FRAMEWORKS/TEMPLATES.**

## 7. Out of scope (Week 5)

- **Node recognizers** (`input`/`output`/`agent`/`router`/`tool`/`retriever`, then
  responder/revisor/evaluator/memory) — Week 6, as `parse()` classmethods beside each
  `codegen()` in `packages/nodes` with a registry-wide property test.
- **Mutation / edit-survival suite** (≥95% survival target) — Week 7.
- **`POST /parse` + editable CodeView + "Apply to canvas" + ceiling-resolution events**
  (`code_edited`, `parse_applied`, `parse_failed`, `parse_degraded`) — Week 8.
- Carry-over loose ends stay tracked in `TODO.md`: Neon prod credential rotation, the Vercel
  preview-build failure, Week-2 follow-ups (FORCE RLS on `run`/`run_usage`, pricing
  re-verification), and the **blind code panel** (non-eng — run it this week in parallel; its
  score decides whether Month-2 buffer goes to codegen quality).
