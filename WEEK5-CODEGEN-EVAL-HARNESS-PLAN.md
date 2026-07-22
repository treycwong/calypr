# Calypr — Week 5 (alt): Codegen quality eval harness (execution plan)

**Date:** 2026-07-13 · **Status:** PLAN · Tracks `MVP-EXECUTION-PLAN.md` Month 1 → the blind
code-panel gate, reframed as a **continuous internal harness**. Sibling to
`WEEK5-ROUNDTRIP-PARSER-PLAN.md` — see §0 for which one Week 5 should be.

## 0. Sequencing decision (read first)

Two candidate Week-5 tracks exist. They are **not** both Week 5:

- **`WEEK5-ROUNDTRIP-PARSER-PLAN.md`** — build the reverse round-trip (the Month-2 thesis).
  Assumes codegen quality is already good enough.
- **This doc** — de-risk that assumption first by building an internal, automated codegen-quality
  gate, since the human blind panel hasn't run and can't be outsourced right now.

**Recommendation:** run this harness's **Layer 1 + Layer 2 (§3–§4) in parallel** with the
round-trip parser — Layer 1 is a few hours and Layer 2 a couple of days, both are pure
test/CI work that doesn't touch the parser. Only make this the *sole* Week-5 focus (deferring
the parser to Week 6) **if** a first harness run scores the generated code poorly — at which
point fixing `services/codegen/generate.py` is the honest priority per the standing kill
condition. This is a real fork; pick it deliberately.

## 1. Why this exists — and its one hard limit

The wedge lives or dies on: *"would a senior engineer merge this generated code?"* The plan's
answer was a **blind panel** of 5–8 outside engineers (≥70% would-merge, ≥4/5 mean). We can't
outsource that right now, so we build an internal AI-driven harness to test the code
continuously instead.

**The limit, stated up front so we don't fool ourselves:** Calypr's product *is* an LLM that
writes code. Judging that code with another LLM grades AI with AI, and LLM judges are lenient
toward LLM code in exactly the ways humans aren't (verbose comments, over-engineering, generic
naming — "impressive garbage," per `ROADMAP-6M.md` §6). Therefore:

- **This harness is the fast, continuous *regression* gate** — "did this change make the code
  worse?" — runnable in CI on every codegen edit.
- **It does NOT replace the human panel** as the *absolute* ≥70% bar. It complements it: the
  humans run rarely and calibrate the harness (§5); the harness runs constantly and catches
  drift. The `MVP-EXECUTION-PLAN.md` gate number stays pinned to the **human** score.

## 2. Verified current state (code audit 2026-07-13) — we're ~60% there

- **Corpus generator exists.** `services/compiler/tests/test_templates.py` already parametrizes
  over `STARTERS` (9 `FRAMEWORKS` + 5 `TEMPLATES`) + `golden.py`, calls `generate_python()`, and
  runs each with `FakeModelClient`. That's the sample set and the "it runs" check already built.
- **Execution/import harness exists.** `services/codegen/tests/test_codegen.py::_import_generated(code, tmp_path)`
  writes generated code to a temp module and imports it; existing tests then call
  `build_graph().invoke(...)`. Reuse verbatim.
- **Ruff already runs at generation time** (`_ruff_format` inside `generate_python`), so
  format-clean is expected — but nothing *asserts* it as a quality gate today.
- **Model seam supports a cross-family judge.** `services/model/src/calypr_model/factory.py`
  `model_for(model_id)` routes by prefix to anthropic / openai / moonshot(kimi) / deepseek /
  fake clients (`ModelClient` Protocol in `base.py`, `.stream(...)`). A judge can run on a
  **different family than the generator** (e.g. generate with gpt-4o-mini, judge with Claude)
  by passing a different id — no new client code. Keyless CI ⇒ `fake` ⇒ harness self-skips the
  LLM layer (mirrors the assistant's keyless pattern).
- **No eval/judge code exists** (grep: no `judge`, no `eval` harness). This is greenfield.

## 3. Layer 1 — mechanical gate (deterministic, no LLM, ~free) · PR-1 (~0.5–1d)

Table stakes: nobody merges code that won't lint, type-check, or run. For every `STARTERS` +
`golden` sample, assert on the `generate_python()` output:

- **Format:** `ruff format --check -` is a no-op (already ruff-formatted; assert it stays so).
- **Lint:** `ruff check -` clean (or a documented, minimal ignore set).
- **Types:** a type-checker passes on the generated module — `pyright` (or `mypy`) run over the
  temp file from `_import_generated`. Add the checker as a dev dep; keyless-safe (pure static).
- **Runs:** imports resolve and `build_graph().invoke(...)`/`run(...)` is green with the fake
  model (reuse the existing template test).
- **Ownable/standalone:** no `import calypr_*` in the generated source (the code is supposed to
  own no Calypr dependency — the docstring already claims it; assert it).

Any sample failing Layer 1 ⇒ automatic **would-not-merge**, no AI required. This alone is a
durable CI regression gate on codegen structure.

**Location:** new `services/codegen/tests/test_quality.py` (mechanical checks live with codegen,
run in the existing `uv run pytest` CI job — no workflow edits).

## 4. Layer 2 — LLM-as-judge, blind + structured · PR-2 (~2d)

For samples that pass Layer 1, score the *subjective* mergeability humans care about. New tiny
package `services/codeeval/` (mirrors `services/codegen` layout; deps `calypr-dsl`,
`calypr-codegen`, `calypr-model`; register in root `pyproject.toml` `workspace.members` +
`testpaths`).

- **`judge(code: str, *, reference: str | None, model_id: str) -> Verdict`** where
  `Verdict(would_merge: bool, confidence: float, scores: dict[str,int], notes: str)` over a
  rubric: idiomatic LangGraph, naming, structure, dead-code/over-commenting, error handling.
- **Blind prompt.** The judge is told it's reviewing a peer's PR — **never** "this was
  AI-generated." (Prompt template lives in-package, versioned, so score changes are traceable to
  rubric changes.)
- **Two variance-killers over naive 1–5 scoring:**
  - **Pairwise vs a hand-written reference.** For each of a handful of archetype graphs
    (input→agent→output, ReAct, RAG, one multi-agent), commit a hand-written reference
    implementation under `services/codeeval/references/`. Ask the judge *"which is more
    mergeable, A or B?"* — relative judgments are far lower-variance than absolute scores, and
    the reference is a fixed yardstick that catches drift.
  - **Cross-family + ensemble.** Judge with a **different model family than the generator** via
    `model_for`, and average 2–3 judge runs, to blunt same-model leniency.
- **Output:** a per-template report (JSON + a short markdown summary) — score per archetype, so
  we see *which* templates generate worse code (e.g. Reflexion vs RAG), which is directly
  actionable on `generate.py` / that node's `codegen()`.
- **Keyless CI:** with `fake`/no keys, Layer 2 self-skips (Layer 1 still gates). Layer 2 is run
  on demand / nightly with a real judge key (a new `CALYPR_CODEEVAL_MODEL` env, unset ⇒ skip),
  **not** on every PR — it costs tokens and is non-deterministic. Cap spend (small fixed corpus;
  the existing `CALYPR_PLATFORM_SPEND_CAP_USD` backstop still applies to any keyed run).

## 5. Layer 3 — human calibration (the anti-self-delusion step)

The harness is only trustworthy if it agrees with humans. So:

- When any human review happens — even a **minimal** one (3 engineers, 5 samples; far cheaper
  than the full panel) — store their would-merge labels alongside the same samples' harness
  verdicts.
- Measure **agreement** (the harness's would-merge rate vs the humans'). Large disagreement ⇒
  the rubric/prompt is recalibrated. This is why humans can't be fully dropped: they're the
  ruler the cheap instrument is calibrated against.
- Track harness score **over time** (commit the JSON reports or a small SQLite/CSV) so a
  codegen change that regresses quality is visible as a trend, not a one-off.

## 6. Verification

- **Layer 1:** `uv run pytest services/codegen/tests/test_quality.py` green across all
  `STARTERS` + `golden`; wired into the existing CI `uv run pytest` + `uvx ruff check .` (no
  workflow edits). A deliberately-broken `generate.py` (e.g. emit an unused import) must turn a
  Layer-1 test red — prove the gate bites.
- **Layer 2:** run `services/codeeval` locally with a real `CALYPR_CODEEVAL_MODEL` over the
  corpus; eyeball the per-template report; confirm keyless run self-skips cleanly in CI.
- No deploy/runtime surface — this is test + tooling only.

## 7. Out of scope (Week 5)

- Wiring harness scores into a dashboard / PostHog (a later nicety; the JSON report is enough
  to read the gate now).
- Auto-fixing low-scoring templates — the harness *reports*; fixing `generate.py` / per-node
  `codegen()` is the follow-on work its scores prioritize.
- Replacing the human blind panel — explicitly **not** a goal (§1). Run the human panel (even
  minimal) at least once to seed Layer 3.
- The reverse round-trip parser — that's `WEEK5-ROUNDTRIP-PARSER-PLAN.md`; see §0 for how the
  two tracks coexist.
