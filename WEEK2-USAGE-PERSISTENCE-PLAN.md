# Calypr — Week 2: Usage Persistence + Durable Checkpointing (execution plan)

**Date:** 2026-07-07 · **Status:** PLAN for implementation · **Tracks:**
`METERING-ANALYTICS-PLAN.md` §5 (the outline this executes) → `MVP-EXECUTION-PLAN.md` Week 2
→ consumed by `PRICING-SPEC.md` (Month-3 credits extend `pricing.py` + these tables).

## 0. Guardrail philosophy (why this is safe to roll out)

Week 2 touches the **hot path** (`/runs` SSE streaming) and the **schema**. Every phase below
is designed to be:

1. **Additive** — new tables, new optional payload keys, new modules. No existing column,
   event shape, or endpoint contract changes.
2. **Best-effort on the hot path** — persistence must NEVER break or delay streaming. If the
   DB is down, runs stream exactly as today (the start.sh "DB-less dev" promise holds).
3. **Default-preserving** — every new env var unset ⇒ today's behavior. No feature flags
   needed because the defaults ARE the flag.
4. **Independently shippable** — three PRs, each green-CI'd, deployed, and prod-verified
   before the next starts. Squash-merged ⇒ each is a one-commit revert if needed.

## 1. Verified current state (code audit 2026-07-07, post PR #2)

- **Usage events flow but evaporate.** Nodes write `{"type":"usage", input_tokens,
  output_tokens}` dicts via the LangGraph custom stream writer
  (`packages/nodes/src/calypr_nodes/_llm.py` ×2, `agent.py` ~line 185) → `run_stream()`
  forwards as `RunEvent(type="usage", state=chunk)` → `runs.py` SSE `{"type":"usage", **state}`.
  **No `node_id`/`model` in the payload; nothing persisted; no `run` table exists.**
- **`create_run` has no `tenant` dep and no DB dependency** — it must stay runnable DB-less.
- **Import gotcha:** `runs.py:16` does `from calypr_api.engine import checkpointer` — a
  *name binding*. A lifespan that reassigns `engine.checkpointer` would be invisible to
  `runs.py`. Must switch to `from calypr_api import engine` + `engine.checkpointer`.
- **Node id is in scope at the right place:** `services/compiler/compile.py:76` —
  `builder.add_node(node.id, node_cls.compile(cfg, node_ctx))`. A wrapper here can carry
  `node.id` into the node's execution (contextvar), with zero node-signature changes.
- **Frontend tolerates extra usage keys:** `apps/web/src/lib/api.ts` types the usage event as
  `{ type: "usage"; [k: string]: unknown }` — additive keys are safe end-to-end.
- **RLS pattern** to copy: migration `0002_agents.py` (`ENABLE ROW LEVEL SECURITY` + policy
  `USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)`).
  Note: with no separate `WITH CHECK`, Postgres applies `USING` to INSERTs too — writers must
  `set_tenant()` on their session. (Today the app role owns the tables so RLS isn't forced on
  it, but write as if `FORCE ROW LEVEL SECURITY` were on — that hardening is coming.)
- **DB-free workspace resolution already exists:** `deps.py::assist_workspace` (dev ⇒ fixed
  dev workspace with no DB; prod ⇒ internal-key + `resolve_workspace`). `/runs` will reuse it.
- **LangGraph checkpoint tables already exist locally** (`checkpoints`, `checkpoint_blobs`,
  `checkpoint_writes`, `checkpoint_migrations`) — `AsyncPostgresSaver.setup()` is idempotent.
- **Neon caveat:** `db/session.py` sets `prepare_threshold=None` because Neon's pooler can't
  hold prepared statements. The checkpointer opens its *own* psycopg connection — it must use
  Neon's **direct (non-pooler) endpoint** or equivalent settings (§4, risk table).

## 2. Phase A — Enrich usage events + `pricing.py` (PR-1: pure additive, zero risk)

**A1. `node_id` via contextvar.** New `packages/nodes/src/calypr_nodes/_context.py`:
`current_node_id: ContextVar[str | None]`. In `compile.py`, wrap each compiled fn:

```python
def _with_node_id(node_id: str, fn: NodeFn) -> NodeFn:
    async def wrapped(state):
        token = current_node_id.set(node_id)
        try:
            return await fn(state)
        finally:
            current_node_id.reset(token)
    return wrapped
builder.add_node(node.id, _with_node_id(node.id, node_cls.compile(cfg, node_ctx)))
```
ContextVars are task-local, so parallel fan-out nodes each see their own id.

**A2. Add `node_id` + `model` to the usage payload** at the three writer sites (`_llm.py` ×2,
`agent.py`): `"node_id": current_node_id.get(None), "model": model_id`. Additive dict keys —
the runtime, SSE layer, and frontend all pass them through unchanged (verified §1).

**A3. `apps/api/src/calypr_api/pricing.py`** — pure module, integrated with nothing yet:
`ModelPrice`, `MODEL_PRICES` (per-direction USD/1M, cache-miss rates — **verify provider
price pages at build time**, don't trust memory), `cost_usd(model_id, in_tok, out_tok)`,
prefix-resolution (`gpt-4o-mini` → its entry), **unknown model ⇒ most-expensive rate
(fail-closed)**, `"fake"` ⇒ $0.

**Gates (PR-1):** full pytest + all Playwright suites green (they exercise the wrapped
compile path); a pytest asserting a fake-model run's usage events carry `node_id`+`model`;
`pricing.py` unit tests (arithmetic, prefixes, fail-closed, fake=0). Deploy → playground
still streams; usage SSE now shows the two new keys.

## 3. Phase B — Schema + best-effort persistence (PR-2: the core)

**B1. Migration `0004_runs`** (down_revision `0003_user_workspaces`), pattern from `0002`:
- `run`: `id` uuid pk default gen_random_uuid, `workspace_id` uuid FK→workspace CASCADE,
  `agent_id` uuid nullable FK→agent SET NULL, `thread_id` text, `status` text
  (`running|completed|errored`), `source` text (`playground|share|api|assist`),
  `input_tokens` int default 0, `output_tokens` int default 0, `cost_usd` numeric(12,6)
  default 0, `created_at`/`finished_at` timestamptz. RLS policy + index
  `(workspace_id, created_at desc)`.
- `run_usage`: `id` uuid pk, `run_id` FK→run CASCADE, `workspace_id` uuid (denormalized for
  RLS), `node_id` text, `model` text, `input_tokens`/`output_tokens` int. RLS policy + index
  `(run_id)`.
- ORM models in `db/models.py` mirroring the above.

**B2. `RunRecorder`** (new `apps/api/src/calypr_api/metering.py`) — the safety wrapper that
makes persistence best-effort:
- `RunRecorder.start(workspace_id, *, agent_id, thread_id, source)` → opens its own session
  (`SessionLocal()`), `set_tenant()`, INSERTs the `run` row, commits. **Any exception ⇒ logs
  one warning and returns a disabled recorder** whose methods are no-ops.
- `.add_usage(payload)` → buffer in memory (no DB per event).
- `.finish(status)` / `.fail()` → bulk-INSERT `run_usage`, UPDATE `run` totals +
  `cost_usd = Σ pricing.cost_usd(model, in, out)`, `finished_at`, commit, close. Exceptions
  swallowed with a warning — **the stream already delivered; metering must not raise.**

**B3. Wire into `create_run`:** add `workspace_id: uuid.UUID = Depends(assist_workspace)`
(rename the dep to `request_workspace` with an alias kept for `/assist` — it's not
assist-specific anymore). Recorder start before streaming, `.add_usage()` on each usage
event, `.finish()`/`.fail()` at the end. `RunRequest` gains optional `agent_id` (additive;
web can send it later — not required for this PR). SSE output: byte-for-byte unchanged.

**B4. Wire into `/assist`:** same recorder, `source="assist"`, usage from the assistant's
`usage` events. This is the moment the AI assistant becomes metered (PRICING-SPEC
requirement + the assistant's deferred follow-up).

**Gates (PR-2):** pytest — fake run writes `run`+`run_usage` rows with correct
node_id/model/tokens/cost; `/assist` writes `source="assist"`; **DB-stopped test:** with
Postgres down, `/runs` still streams tokens + `[DONE]` (recorder disables itself); RLS
isolation across two workspaces. All e2e suites green (CI has Postgres). Deploy → run once in
prod, `SELECT * FROM run ORDER BY created_at DESC LIMIT 1` in Neon console shows the row with
a sane `cost_usd`.

## 4. Phase C — Durable checkpointer + spend kill-switch (PR-3)

**C1. Fix the import binding first:** `runs.py` → `from calypr_api import engine`, use
`engine.checkpointer` at call time.

**C2. FastAPI lifespan** in `main.py`: on startup, try
`postgres_checkpointer(settings.database_url)` (enter the async context via
`AsyncExitStack`), `await cp.setup()` (idempotent), then `engine.checkpointer = cp`. On any
failure ⇒ keep the `InMemorySaver` and log a warning (keyless CI / DB-less dev unchanged).
On shutdown, unwind the stack.

**C3. Neon pooler risk:** the checkpointer's psycopg connection must not use prepared
statements through the pooler. Mitigation, in order: (a) point it at Neon's **direct**
endpoint via a new optional `CALYPR_CHECKPOINT_DATABASE_URL` (falls back to `database_url`);
(b) if the AsyncPostgresSaver API accepts connection kwargs, pass
`prepare_threshold=None`. Verify against the installed `langgraph-checkpoint-postgres`
source (don't trust memory). If neither works cleanly in a day, ship PR-3 without C2/C3
(kill-switch only) and file the checkpointer separately — it's a hardening step, not a gate
for Week 2's metering goal.

**C4. Spend kill-switch** (PRICING-SPEC §9): `CALYPR_PLATFORM_SPEND_CAP_USD` (unset/0 ⇒
disabled). In `create_run` + `create_assist`, before starting: if enabled, check
`SELECT coalesce(sum(cost_usd),0) FROM run WHERE created_at >= date_trunc('month', now())`
— **cached in-process for 60s** so the hot path adds at most one cheap query/min — and if
over cap, yield the SSE error event (same shape as the assist cap) instead of running.
DB unreachable ⇒ fail-open (availability over enforcement, pre-billing).

**Gates (PR-3):** pytest — cap trips at the boundary (monkeypatched settings + seeded rows);
fail-open when DB down; keyless e2e green (fallback checkpointer). Prod verify: send a
playground message, restart the Railway service, continue the same thread → history intact.

## 5. What could break — and the specific mitigation

| Risk | Mitigation |
|---|---|
| SSE contract change breaks playground/e2e | Phase A adds *keys* only; B/C don't touch event shapes. e2e phase2/5/9 run in every PR. |
| DB-less local dev stops working (start.sh promise) | `request_workspace` is DB-free in dev; `RunRecorder` self-disables on connect failure; checkpointer falls back to in-memory. Explicit pytest for the DB-down stream. |
| RLS blocks metering inserts | Recorder calls `set_tenant()` on its own session before writing; `workspace_id` denormalized onto `run_usage`. |
| Lifespan checkpointer swap invisible to `runs.py` | C1 fixes the name-binding import *before* the swap lands. |
| Neon pooler × prepared statements breaks the checkpointer | Direct-endpoint URL (`CALYPR_CHECKPOINT_DATABASE_URL`) / verified kwargs; C2 is droppable without blocking the PR. |
| Metering slows or kills streaming | Usage buffered in memory; DB writes only at start/finish; all recorder exceptions swallowed after one warning. |
| Migration fails on populated Neon | Tables are new (purely additive); test `upgrade head` locally on both an empty DB and a copy with existing rows; Railway preDeploy runs it atomically. |
| Wrong prices → wrong `cost_usd` | Prices re-verified at build time from provider pages; unknown-model fail-closed test; margin re-check is a Month-3 (credits) concern — this pass only *records*. |

## 6. Rollout sequence

1. **PR-1 (Phase A)** — enrichment + pricing. Merge → deploy → confirm playground streams and
   usage events carry `node_id`/`model` in prod.
2. **PR-2 (Phase B)** — migration + recorder + `/runs` + `/assist` wiring. Merge → Railway
   auto-migrates → run once in prod → verify the `run`/`run_usage` rows in Neon.
3. **PR-3 (Phase C)** — checkpointer (droppable) + kill-switch. Merge → restart-survival
   check → set `CALYPR_PLATFORM_SPEND_CAP_USD` on Railway (e.g. `100`).

Each PR: full pytest + all Playwright suites + ruff green before merge; squash-merge ⇒
single-commit revert. No coordinated web deploy needed at any step (the web app is untouched
except optionally sending `agent_id` later).

## 7. Non-goals (deliberately excluded)

Credits/ledger/BYOK/402 enforcement (Month 3 — extends `pricing.py` + these tables);
share links (Week 3); a user-facing usage meter (Week 10 pricing surface); passing cached-token
discounts through; per-workspace caps beyond the existing assist daily cap (the platform-wide
kill-switch supersedes nothing and adds the loss firewall).
