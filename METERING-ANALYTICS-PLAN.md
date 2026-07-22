# Calypr — Metering & Analytics Plan (MVP Weeks 1–2)

**Date:** 2026-07-07 · **Status:** PLAN for implementation · **Tracks:**
`MVP-EXECUTION-PLAN.md` Month 1, Weeks 1–2 (analytics + usage persistence + durable
checkpointing); prerequisite for `PRICING-SPEC.md` (the credit ledger extends this).

## 1. What this is (plain English)

Two foundational systems the whole business model sits on:

- **Analytics (PostHog)** — record *what users do*, especially the **"ceiling events"**: the
  moments a user opens / copies / downloads the generated Python. Calypr's thesis is
  "design on a canvas, **leave with the code you own**" — these events are how the founder
  *measures* whether people actually hit that ceiling and take the code. Without them the
  Month-2 gate is unreadable.
- **Metering (usage persistence)** — write a durable row for **every run**: which agent, how
  many input/output tokens per node, which model, and the **USD cost**. Today token counts
  stream to the playground and vanish — there is no `run` table at all. This table is what
  billing later reads (`SELECT sum(cost_usd) …`), what caps the AI Assistant we just shipped,
  and what proves "positive gross margin per run."

Plus one hardening step bundled in: **durable checkpointing** so a conversation survives a
Railway restart (today it's in-memory and lost on redeploy).

**Why this is the next build (not RAG):** it's the top of the MVP plan; billing (Month 3) is
literally a `SELECT` over these tables; and the **AI Assistant is currently unmetered** —
PRICING-SPEC treats it as a credit spender, so this closes a live margin risk and the two
follow-ups that feature left open (usage persistence + PostHog).

## 2. Existing contracts to build on (read these first)

| Contract | File | State today |
|---|---|---|
| `Usage` event (`input_tokens`, `output_tokens`) | `services/model/src/calypr_model/events.py` | ✅ exists; **no `node_id`/`model`** |
| Usage writers (stream `{"type":"usage",…}`) | `packages/nodes/src/calypr_nodes/_llm.py` (`actor_message`, `collect_text`) + `agent.py` (~line 185) | ✅ emit; enrich here |
| Streaming run → `RunEvent(type="usage", state=…)` | `services/runtime/src/calypr_runtime/{run.py,events.py}` | ✅ passes usage through |
| SSE run endpoint | `apps/api/src/calypr_api/routers/runs.py::create_run` | ✅ streams; **no `tenant` dep, no persistence** |
| In-memory checkpointer (module global) | `apps/api/src/calypr_api/engine.py` | 🟡 hardcoded `InMemorySaver()` |
| Postgres checkpointer factory | `services/runtime/src/calypr_runtime/checkpoint.py::postgres_checkpointer` | ✅ exists, unused |
| ORM + RLS pattern | `apps/api/.../db/models.py`, migration `0002_agents.py` | add `run`, `run_usage` here |
| Tenant dep (`workspace_id`) | `apps/api/src/calypr_api/deps.py::tenant` | ✅ reuse |
| Analytics seam (`track()` no-op) + assistant call sites | `apps/web/src/lib/analytics.ts` | 🟡 stub; wire to PostHog |
| Ceiling / run / template surfaces | `CodeView.tsx`, `Playground.tsx`, `TemplatesPanel.tsx` | instrument here |
| `/assist` usage events (already emitted) | `apps/api/.../routers/assist.py` | persist with `source="assist"` |

## 3. Architecture

```
WEB analytics:  track(event, props)  ──▶  posthog-js (client)         ┐
                server capture(event, workspace_id)  ──▶ PostHog API  ┘  ceiling/run/paywall events

METERING:  node LLM call → usage{node_id, model, in, out}  (enriched at source)
   → runtime run_stream (RunEvent usage) → routers/runs.py::create_run:
        1. INSERT run (workspace_id, agent_id?, thread_id, status="running", source)
        2. stream; accumulate usage rows in memory
        3. finalize: INSERT run_usage[], UPDATE run (tokens, cost_usd via pricing.py, status)
   (same hook serves /assist with source="assist")

CHECKPOINTER:  FastAPI lifespan → postgres_checkpointer(DATABASE_URL).setup()
   → engine uses it; in-memory fallback when no DB (keyless CI).
```

## 4. Week 1 — Analytics + hygiene

### 4a. PostHog wiring (~1.5d)
- Add **`posthog-js`**; a client `PostHogProvider` mounted in `apps/web/src/app/layout.tsx`
  (env: `NEXT_PUBLIC_POSTHOG_KEY`, `NEXT_PUBLIC_POSTHOG_HOST`). No-key ⇒ no-op (dev/CI safe).
- Implement `analytics.ts::track()` against `posthog-js`; **expand the `AnalyticsEvent`
  union** beyond the 4 assistant events with the ceiling/run/template set below. The assistant
  already calls `track(...)` — those light up for free.
- **Instrument the ceiling surfaces:**
  - `CodeView.tsx` → `code_view_opened`, `code_copied`, `code_downloaded` **(THE ceiling
    events — the thesis metric).**
  - `Playground.tsx` → `run_started`, `run_completed`, `run_errored`.
  - `TemplatesPanel.tsx` → `template_selected`.
- **Server-side `capture()` helper** in `apps/api` (thin PostHog client) keyed by
  `workspace_id` from the `tenant` dep — for events best trusted server-side (e.g. `run_persisted`,
  cost). Optional in W1; needed once billing events matter.
- **Done:** events visible in PostHog from prod.

### 4b. Hygiene (~0.5d) — closes TODO.md 🔴/🟢
- **Revoke the old exposed OpenAI key** in the OpenAI dashboard (TODO.md 🔴 still open).
- **Bump the deprecated Node-20 GitHub Actions** in `.github/workflows/ci.yml`
  (`actions/checkout@v4`, `actions/setup-node@v4`, `astral-sh/setup-uv@v5`,
  `pnpm/action-setup@v4`).

## 5. Week 2 — Usage persistence + durable checkpointing (~4d)

> **Execution detail:** `WEEK2-USAGE-PERSISTENCE-PLAN.md` — phased (3 PRs), with the verified
> code-audit facts, breakage-risk table, and per-PR rollout gates. Week 1 (§4) shipped in PR #2.

### 5a. Enrich usage at the source
Add `node_id` + `model` to the usage payload where it's written — `_llm.py` (both
`actor_message` and `collect_text`) and `agent.py`. The node's `fn_name`/id and its `model_id`
are already in scope at the call site; thread them into the `{"type":"usage", …}` dict. Widen
`calypr_model.Usage` (or the stream payload) to carry them. Everything downstream already
forwards the payload, so no runtime/API changes are needed to *transport* the new fields.

### 5b. Tables + models — migration `0004_runs`
> **Migration number:** this takes **`0004`** (MVP sequence: `0004_runs` → `0005_share_links`
> → `0006_billing`). The RAG plan's KB migration shifts to a later number accordingly.

- **`run`**: `id`, `workspace_id` (FK + RLS per `0002`), `agent_id` (nullable FK),
  `thread_id`, `status` (`running|completed|errored`), `source`
  (`playground|share|api|assist`), `input_tokens`, `output_tokens`, `cost_usd` (numeric),
  `created_at`, `finished_at`.
- **`run_usage`**: `id`, `run_id` (FK ON DELETE CASCADE), `workspace_id` (denormalized for
  RLS), `node_id`, `model`, `input_tokens`, `output_tokens`.
- RLS `USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)` on both;
  SQLAlchemy models in `db/models.py`.

### 5c. `pricing.py` (cost only — the credit layer extends it later)
New `apps/api/src/calypr_api/pricing.py` with the **single price table** from PRICING-SPEC §3:
```python
MODEL_PRICES: dict[str, ModelPrice]        # USD per 1M tokens (cache-miss), per provider
def cost_usd(model_id, in_tok, out_tok) -> Decimal   # sum over per-direction rates
```
Unknown model ⇒ **fail-closed** (most-expensive rate). A pytest pins the arithmetic. The
`credit_rate`/`debit_micro` + ledger (PRICING-SPEC) build on this module in Month 3 — don't
add credits now.

### 5d. Persist in `create_run`
- Add the missing **`tenant` dep** to `create_run`; optional `agent_id` on `RunRequest`
  (`schemas.py`).
- Row lifecycle inside `event_stream()`: INSERT `run` (`status="running"`) before streaming →
  accumulate each `usage` event → on `final`, INSERT `run_usage[]` and UPDATE `run` with token
  totals, `cost_usd = Σ cost_usd(model, in, out)`, `status`, `finished_at`. On exception →
  `status="errored"`.
- **Reuse the same hook for `/assist`** (`source="assist"`) so the assistant is metered from
  day one — this is the PRICING-SPEC requirement and the assistant's deferred follow-up.

### 5e. Durable Postgres checkpointer
Wire `postgres_checkpointer(settings.database_url)` in a **FastAPI lifespan** in `main.py`
(call `.setup()` once), replacing the module-global `InMemorySaver` in `engine.py`. Keep the
in-memory fallback when there's no DB (keyless CI) — mirror the graceful-degradation pattern
already used for `/assist`.

### 5f. (Recommended) Platform spend kill-switch — PRICING-SPEC §9
Once `run.cost_usd` exists, add `CALYPR_PLATFORM_SPEND_CAP_USD` (start $100): the enforcement
points check `SELECT sum(cost_usd) FROM run WHERE source != 'byok' AND month = current`; when
tripped, platform-key runs + assist calls `402` for everyone (BYOK unaffected). This is the
real loss firewall protecting the now-live, billed assistant — cheap to add here, and it
supersedes the assistant's in-memory daily cap.

## 6. Tests — "done" gates (MVP)

- **pytest:** a fake-model run writes correct `run` + `run_usage` rows (node_id/model/tokens);
  `cost_usd` arithmetic + fail-closed unknown model; RLS isolates `run`/`run_usage` across two
  workspaces; `/assist` writes a `source="assist"` row.
- **Durability:** a thread's history survives swapping the checkpointer (Postgres path);
  in-memory fallback still works keyless.
- **Playwright / prod smoke:** PostHog receives `code_view_opened` etc. from prod; a real run
  produces a `run` row (checked via an internal endpoint or DB).

## 7. Production / shipping

- **Migration `0004` runs automatically** on Railway (`alembic upgrade head` preDeploy) against
  Neon — schema-changing, so test locally on empty + populated DBs first (like RAG).
- **`uv.lock` committed** (no new *Python* runtime deps beyond what's present — `posthog-js` is
  web-only; a server `posthog` client is optional). Web adds `posthog-js` → `pnpm-lock.yaml`.
- **New env:** Vercel — `NEXT_PUBLIC_POSTHOG_KEY`/`_HOST`; Railway — optional `POSTHOG_API_KEY`
  (server capture), `CALYPR_PLATFORM_SPEND_CAP_USD`. All no-op if unset (safe default).
- **No behavior break:** metering is write-only in Weeks 1–2 (no enforcement/402 yet — that's
  Month 3 billing), so shipping it can't block existing runs.

## 8. Non-goals (this pass — they build on this)

Credit ledger / debits / BYOK / plan-cap `402`s (PRICING-SPEC, Month 3 — extends `pricing.py`
+ adds `credit_ledger`); Stripe; share links (Week 3, separate); passing cached-token discounts
through; the pricing web surface / upgrade modal. This pass is **measurement + a durable
ledger**, not enforcement.

## 9. MVP / TODO mapping

| Section | MVP-EXECUTION-PLAN | TODO.md |
|---|---|---|
| 4a PostHog | Week 1 (analytics) | — |
| 4b Hygiene | Week 1 (hygiene) | 🔴 revoke key · 🟢 bump Actions |
| 5a–5d Usage persistence + `pricing.py` | Week 2 | (unblocks assistant metering follow-up) |
| 5e Durable checkpointer | Week 2 | — |
| 5f Spend kill-switch | PRICING-SPEC §9 | (protects the shipped assistant) |
```
