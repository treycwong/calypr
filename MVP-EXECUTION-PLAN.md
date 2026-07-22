# Calypr — MVP Execution Plan (12 weeks)

**Date:** 2026-07-02 · **Status:** DRAFT for review · Downstream of
[`ROADMAP-6M.md`](./ROADMAP-6M.md) / [`OFFICE-HOURS.md`](./OFFICE-HOURS.md) — this is the
execution of the settled strategy, not a new strategy doc.

## Context

Calypr is a multi-tenant SaaS: a visual agent canvas (Next.js + React Flow) → versioned DSL
(GraphSpec) → LangGraph compiler + ownable Python codegen → hosted runtime (FastAPI, SSE),
live at www.calypr.co (Vercel → Railway → Neon/pgvector, RLS multi-tenancy).

Decisions baked in (per founder): validation gates included alongside build, **reverse
round-trip is the lead differentiator**, Stripe lands in month 3.

**Verified current state (code audit, not doc claims):**

- ✅ Built: 12 node types; compiler + validation; codegen to standalone ruff-formatted Python;
  SSE streaming runtime (in-process); fake/OpenAI/Anthropic model seam; RLS multi-tenancy;
  Better Auth; polished canvas (rail, Properties/Code tabs, Try-it playground); templates;
  Playwright e2e gates 0–6; auto-deploy prod pipeline.
- ❌ Zero code: reverse round-trip (the thesis), analytics/ceiling-event instrumentation,
  share links, Stripe, AI-assistant backend (UI scaffold disabled), KB ingestion.
- 🟡 Partially built (closer than the roadmap doc assumed):
  - **Usage events** flow end-to-end (`services/model/events.py` → `packages/nodes/_llm.py` →
    `runtime/run.py` → SSE in `apps/api/routers/runs.py`) but lack `node_id`/`model` and are
    never persisted — there is no `run` table at all.
  - **Postgres checkpointer** exists (`services/runtime/src/calypr_runtime/checkpoint.py`) but
    `apps/api/src/calypr_api/engine.py` hardcodes `InMemorySaver` — one wiring change.
  - **Golden fixtures** (`services/compiler/src/calypr_compiler/golden.py`) are ready to power
    round-trip property tests.

---

## Month 1 — Instrument, measure, share (Weeks 1–4)

Thesis-validation infrastructure. Nothing speculative — all of it is required to even read
the Month 2/3 gates.

### Week 1 — Blind code panel + analytics
- **Panel (non-eng, ~2d):** generate code via existing `POST /codegen` for 4–5 specs spanning
  the ladder (golden builders + Market Research / Reflexion templates in
  `services/compiler/templates.py`); 5–8 senior engineers review blind. Target ≥70%
  would-merge, ≥4/5 mean.
- **PostHog (~1.5d):** provider in `apps/web/src/app/layout.tsx`; capture in `CodeView.tsx`
  (`code_view_opened` / `code_copied` / `code_downloaded` — these ARE the ceiling events),
  `Playground.tsx` (`run_started/completed/errored`), `TemplatesPanel.tsx`
  (`template_selected`); thin server `capture()` helper in `apps/api` keyed by workspace id
  from the existing `tenant` dep.
- **Hygiene (~0.5d):** revoke the old exposed OpenAI key (TODO.md 🔴); bump GitHub Actions
  versions in `.github/workflows/ci.yml` (TODO.md 🟢).
- **Done:** events visible in PostHog from prod; panel invitations out.

### Week 2 — Usage persistence + durable checkpointing (~4d)
- Enrich usage payloads with `node_id` + `model` at the source:
  `packages/nodes/src/calypr_nodes/_llm.py` (both writers) and `agent.py`.
- Alembic `0004_runs.py`: `run` (workspace_id, agent_id?, thread_id, status, timestamps,
  input/output token totals, cost_usd, source: `playground|share|api`) + `run_usage`
  (run_id, node_id, model, tokens) — RLS pattern from `0001_baseline.py`; SQLAlchemy models in
  `apps/api/src/calypr_api/db/models.py`.
- Hook in `routers/runs.py::create_run`: create row before streaming → accumulate `usage`
  events inside `event_stream()` → finalize with cost from a static price table
  (new `apps/api/src/calypr_api/pricing.py`). Add the missing `tenant` dep to `create_run`;
  optional `agent_id` on `RunRequest` in `schemas.py`.
- Wire `postgres_checkpointer()` in a FastAPI lifespan (`main.py`), replacing the
  module-global `InMemorySaver` in `engine.py`; keep the in-memory fallback for keyless CI.
- **Done:** pytest asserts a fake-model run writes correct `run`/`run_usage` rows; a prod
  thread survives a Railway restart.

### Week 3 — Share-to-test links (~4d)
- Alembic `0005_share_links.py`: `share_link` (token unique, agent_id, workspace_id,
  created_at, revoked_at, run_cap). Token reads use a documented RLS bypass
  (SECURITY-DEFINER-style lookup); management endpoints stay RLS-scoped.
- API: `POST/DELETE /agents/{id}/share` in `routers/agents.py`; new `routers/share.py` —
  `GET /share/{token}` (agent name only, never the spec) + `POST /share/{token}/runs` (loads
  `graph_spec` server-side, streams via the same `run_stream`, meters rows with
  `source="share"`, enforces `run_cap`).
- Web: `apps/web/src/app/s/[token]/page.tsx` reusing `Playground.tsx` with a `shareToken`
  prop hitting a new `/api/s/[token]/runs` proxy; Share button in the canvas top bar.
  Events: `share_created`, `share_run`.
- **Done:** Playwright `phase7-share.spec.ts` — create agent → share → open link logged-out →
  streamed reply; cap enforced (4xx after cap).

### Week 4 — Partner-readiness polish + buffer (~3d)
- React error boundary around canvas/playground; toasts on failed saves/runs.
- One more ceiling-inducing template in `services/compiler/templates.py` if partner calls
  reveal a gap (templates are cheap: pure GraphSpec builders).
- **Kill-condition buffer:** if the panel scores <70% would-merge, this week (and as much of
  Month 2 as needed) goes to codegen quality in `services/codegen/generate.py` + per-node
  `codegen()` — honor the gate, no exceptions.
- **Month 1 gate:** panel ≥70% AND ≥10 design partners with a real agent running AND
  cost/ceiling events flowing.

---

## Month 2 — Reverse round-trip (Weeks 5–8) — the existential track

Everything else pauses. This makes the "no-ceiling" promise technically true.

### Architecture (decided before Week 5)

Candidates for code → GraphSpec:

| Approach | How | Pros | Cons |
|---|---|---|---|
| **A. Spec-embedded-in-code** | Emit GraphSpec JSON as comment/sidecar; "parse" = read it back | Trivial, lossless metadata | Doesn't parse *edits* — a cache, not a round-trip |
| **B. Marker regions** | `# calypr:begin node=...` fences; extract regions | Simple, edit-tolerant inside fences | Machine fences litter the "senior engineer wrote this" artifact; brittle under reformat |
| **C. AST parse of known shapes** | `ast.parse`; recover topology from `build_graph()`, config from node function bodies | Code stays pristine; robust to formatting; genuinely parses edits | Most work; needs a recognizer per node type |

**Pick: C for structure + a thin A anchor for what code can't express.**

- `build_graph()` in `generate.py` is emitted from a closed grammar (only `add_node`,
  `add_edge`, `add_conditional_edges`, string literals, `START`/`END`) — an AST walker
  recovers nodes/edges/entry/conditions mechanically, even after hand edits in the same idiom.
- Per-node config recovery via a `parse()` classmethod beside each node's `codegen()` in
  `packages/nodes` — the inverse lives next to the forward so they can't drift (enforced by a
  registry-wide property test).
- **Graceful degradation (what makes ≥95% survival achievable):** any function body no
  recognizer matches becomes a `code` (Custom Code) node with the body preserved verbatim.
  The parser never hard-fails on the generated surface — an unrecognizable edit degrades one
  node instead of rejecting the file. This is the "constrained surface, not a general Python
  parser" mandate in code form.
- The A anchor: one `# calypr: {"schema_version":…, "layout":…, "labels":…}` trailer (or
  sidecar) carrying canvas positions/labels. If the user deletes it, parsing still succeeds
  and the existing left-to-right auto-layout applies.

### Weekly deliverables

> **Week 5 fork (decide deliberately):** two candidate tracks exist —
> `WEEK5-ROUNDTRIP-PARSER-PLAN.md` (the parser below) and
> `WEEK5-CODEGEN-EVAL-HARNESS-PLAN.md` (an internal AI gate substituting for the un-run blind
> panel). They are not both Week 5. Default: run the harness's mechanical + judge layers *in
> parallel* with the parser; make the harness the sole Week-5 focus (deferring the parser) only
> if a first run scores codegen poorly. See that doc's §0. The ≥70% gate stays pinned to a human
> review, not the AI harness.

- **Week 5 (~4d):** new `services/roundtrip` package —
  `parse_python(code) -> ParseResult(spec, warnings, degraded_nodes)`; `build_graph()` +
  `State` class AST walkers (channels/reducers: `Annotated[list, add_messages]` ↔ `messages`,
  `operator.add` ↔ append reducer); emit the metadata trailer from `generate.py`.
  **Done:** topology round-trips for every graph in `golden.py` + all FRAMEWORKS/TEMPLATES.
- **Week 6 (~5d):** node recognizers in priority order: `input`, `output`, `agent`, `router`,
  `tool`, `retriever` (covers every shipped template), then
  `responder`/`revisor`/`evaluator`/`memory`; fallback-to-`code`-node for misses.
  **Done:** registry-wide property test `parse_python(generate_python(spec)).spec == spec`
  (equivalence modulo layout) for every registered node type.
- **Week 7 (~4d):** mutation/edit-survival suite — programmatically apply realistic edits
  (change a prompt, tweak temperature, add an edge line, insert a hand-written node, delete
  the trailer, reformat with black) and assert ≥95% parse survival with correct degradation.
  Document the equivalence relation in the package README (becomes OSS-launch content).
  **Done:** mutation suite green in CI; survival measured, not vibes.
- **Week 8 (~4d):** ship the loop — `POST /parse` in new `routers/roundtrip.py`;
  `CodeView.tsx` gains an editable mode + **"Apply to canvas"** (warnings inline; degraded
  nodes render as the existing Code node). Events: `code_edited`, `parse_applied`,
  `parse_failed`, `parse_degraded` — the ceiling-resolution metrics. Playwright
  `phase8-roundtrip.spec.ts`: open template → edit prompt in code tab → apply → canvas
  updates → run streams.
- **Month 2 gate:** round-trip works for the core node set AND ≥50% of code-droppers stay
  14+ days AND 30-day retention ≥40%.

---

## Month 3 — Charge money + OSS launch (Weeks 9–12)

### Week 9 — Stripe billing core (~4d)
- Alembic `0006_billing.py`: workspace gains `stripe_customer_id`, `plan` (`free|pro`),
  `run_limit`.
- New `routers/billing.py`: checkout-session creation + webhooks
  (`checkout.session.completed`, `customer.subscription.updated/deleted`) flipping `plan`.
  Stripe stays entirely in the FastAPI layer (secrets already live on Railway); web proxies
  via `apps/web/src/app/api/billing/`.
- **Enforcement:** in `create_run` and the share route, check current-month aggregates from
  the Week-2 `run` table against plan caps → 402 with an upgrade payload. Free tier
  token-capped; cheap-model routing for anonymous share runs.
- **Done:** test-mode e2e — hit free cap → 402 → checkout → webhook → runs resume.

### Week 10 — Pricing surface + margin dashboard (~3d)
- Pricing page + billing section in `dashboard/settings` (plan, usage meter, upgrade).
- Founder-facing margin view: revenue vs `sum(cost_usd)` per workspace (internal endpoint +
  SQL is enough — the gate is "positive gross margin per run"; you just need to read it).
- **Done:** a real design partner upgrades with a real card.

### Week 11 — OSS DSL + codegen launch (~4d)
- Apache-2.0. Standalone READMEs + PyPI for `packages/dsl`, `services/codegen`, **and
  `services/roundtrip`** — shipping the bidirectional pair is the differentiated Show HN:
  *"a versioned graph spec ⇄ LangGraph Python."*
- Verify the packages import clean of private deps from a fresh venv; demo GIF =
  canvas → code → edit → canvas.
- **Done:** `pip install calypr-dsl calypr-codegen` works from a clean venv; Show HN posted.

### Week 12 — Buffer + gate review
- Whatever the 11 weeks displaced: recognizer gaps found by real users, billing edge cases.
- Minimal KB slice **only if ≥3 design partners are blocked on real RAG data** — scope is the
  first two TODO 🟡 bullets only (`knowledge_base`/`kb_chunk` migration + upload→chunk→embed
  endpoint with the `fake|openai` embeddings seam); no KB UI beyond a file input.
- **Month 3 gate:** ≥25 paying workspaces AND positive gross margin per run AND one
  sub-segment converting ~3×. Below the bar → iterate the wedge, don't scale.

---

## Explicitly NOT in these 12 weeks

- **Dynamic fan-out / LangGraph `Send`** (TODO 🟣) — new engine primitive, zero validation
  value now, and it would expand the reverse-parse surface mid-build. Month 4+.
- **AI-assistant backend** — `AssistantPanel.tsx` stays disabled. Most token-hungry,
  margin-riskiest feature; the roadmap puts the copilot in Month 4 behind the paid tier.
- **Full RAG ingestion + KB UI** — only the conditional Week-12 slice. Chroma provider and
  RAG-as-tool (🔵): no.
- **Undo/redo, state editor, versioning/branches, real-time collab** — Month 5 data-picked fork.
- **General Python parser** — approach C is designed so it's never needed.
- **Marketplace, per-agent public API beyond share links, SSO/enterprise, SOC 2, vertical 2.**

## Verification

- Every week ends with a concrete gate: pytest (usage rows, round-trip property + mutation
  suites), new Playwright specs (`phase7-share`, `phase8-roundtrip`) added to the existing
  `pnpm e2e` gate, prod smoke checks (restart survival, PostHog events, Stripe test-mode flow).
- Month gates are the ROADMAP-6M kill conditions read from real data: panel score,
  ceiling-event resolution in PostHog, margin from the `run` table.

## Sequencing logic

Panel first — it can kill everything for the price of coffees. Metering/analytics/share
before round-trip because the Month-2 gate is unreadable without events, and Week-9 billing
enforcement is a `SELECT sum(...)` over the Week-2 `run` table. Round-trip gets an
uninterrupted 4-week block because it is the thesis and it is genuinely hard. Billing lands
last-but-before-buffer because charging with no round-trip is charging for a demo.

## Critical files

- `services/codegen/src/calypr_codegen/generate.py` — the closed grammar the reverse parser
  inverts; metadata trailer lands here.
- `apps/api/src/calypr_api/routers/runs.py` — usage persistence, tenant scoping, billing
  enforcement, and share runs all hook into `create_run`.
- `packages/nodes/src/calypr_nodes/_llm.py` — usage-event enrichment (node_id/model) at the source.
- `apps/api/src/calypr_api/db/models.py` — new `run`, `run_usage`, `share_link`, billing
  columns (RLS pattern from migrations 0001/0003).
- `apps/web/src/components/canvas/CodeView.tsx` — the ceiling surface: instrumentation in
  Week 1, editable + "Apply to canvas" in Week 8.
