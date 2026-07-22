# Calypr — Week 3: Share-to-test links (execution plan)

**Date:** 2026-07-09 · **Status:** PLAN for implementation · **Tracks:**
`MVP-EXECUTION-PLAN.md` Week 3 → builds directly on Week 2's metering
(`WEEK2-USAGE-PERSISTENCE-PLAN.md`, shipped: `run`/`run_usage`, `RunRecorder`, `run_stream`,
durable pooled checkpointer, `CALYPR_PLATFORM_SPEND_CAP_USD`).

**Goal:** an agent owner mints an unguessable link; anyone (logged-out) opens it, runs the
agent, and sees streamed replies — **without ever receiving the GraphSpec** — capped per link
and metered as `source="share"` rows.

## 0. Guardrail philosophy (why this is safe to roll out)

Week 3 adds **public, unauthenticated** surface — the highest-risk thing we've shipped. Every
phase is designed to be:

1. **Additive & isolated** — one new table (`share_link`), one new router (`share.py`), new
   public web routes under `/s/[token]`. No existing endpoint's contract changes.
2. **Spec never leaves the server** — the public endpoints return the agent *name* and the run
   *output* only. `graph_spec` is loaded server-side inside the run handler and never
   serialized to the client. An e2e assertion enforces this.
3. **Public by design — no auth grafted onto existing routes.** *Lesson from Week 2's #5
   regression:* adding a tenant dep to a route that the web proxy calls without headers 401s in
   prod. Share endpoints therefore carry **no workspace dependency**, and the `/api/s/*` web
   proxies **do not** forward `internalHeaders()`. Management endpoints (mint/list/revoke) stay
   fully RLS-scoped under the existing `tenant` dep.
4. **Bounded blast radius** — each link has a `run_cap` (atomic), links are revocable, and the
   Week-2 platform spend kill-switch is the global backstop for anonymous model spend.
5. **Independently shippable** — three squash-merged PRs, each green-CI'd and prod-verified
   before the next (per Week-2's proven cadence).

## 1. Verified current state (code audit 2026-07-09, post Week 2 / PR #8)

- **Migrations head is `0004_runs`** (`apps/api/migrations/versions/`). Week 3 adds
  `0005_share_links` with `down_revision = "0004_runs"`.
- **RLS-bypass precedent exists:** `0003_user_workspaces` defines `resolve_workspace(text)` as a
  `SECURITY DEFINER` SQL function with `SET search_path = pg_catalog, public`. Token lookups
  (anonymous, no `calypr.workspace_id` GUC) copy this exact pattern — a documented, auditable
  bypass, not reliance on the app role's owner privilege.
- **`RunRecorder`** (`apps/api/src/calypr_api/metering.py`) already takes
  `start(workspace_id, *, source, agent_id=None, thread_id=None)` and is best-effort
  (self-disables on DB failure). `source="share"` is a new value; the column is free-text.
- **`run_stream`** (`calypr_runtime`) is source-agnostic: `run_stream(graph, ctx, message,
  thread_id=, checkpointer=)`. Share reuses it verbatim, with `context_for(graph)` and
  `engine.checkpointer` (durable, pooled — Week 2 #7).
- **Owner-scoping helper** in `routers/agents.py`: `_get_owned(session, workspace_id, agent_id)`
  raises 404 if the agent isn't in the tenant's workspace. Mint/revoke reuse it.
- **SSE error envelope** is `{"type":"error","message":...}` + `data: [DONE]` (see `runs.py`).
  Share reuses it for revoked/cap/not-found so the web playground renders errors unchanged.
- **Web run path:** `apps/web/src/lib/api.ts::runAgent` → `streamSSE("/api/runs", {graph,
  message, thread_id}, onError)`; `apps/web/src/app/api/runs/route.ts` pipes the API's SSE back.
  `Playground.tsx` (`apps/web/src/components/canvas/`) is the run UI to reuse via a `shareToken`
  prop. Share adds a **spec-free** variant: body is `{message, thread_id}` only.
- **e2e** lives in `e2e/tests/phaseN.spec.ts` (Playwright). New spec: `phase7-share.spec.ts`.
- **Auth:** Better Auth session drives `internalHeaders()` (server-side). Mint/list/revoke go
  through the authenticated web proxies (which already forward those headers, like `/agents`).

## 2. Phase A — `share_link` schema + mint/list/revoke (PR-1: authenticated, additive)

**A1. Migration `0005_share_links`** (down_revision `0004_runs`), RLS pattern from `0002`:
- `share_link`: `id` uuid pk default `gen_random_uuid()`, `token` text **unique not null**,
  `agent_id` uuid FK→agent CASCADE not null, `workspace_id` uuid FK→workspace CASCADE not null,
  `run_cap` int nullable (NULL ⇒ unlimited), `run_count` int not null default 0,
  `created_at` timestamptz default now(), `revoked_at` timestamptz nullable. RLS policy
  (`workspace_id = current_setting('calypr.workspace_id', true)::uuid`) + index on
  `(workspace_id)`. `token` is already uniquely indexed.
- ORM `ShareLink` in `db/models.py` mirroring the above.

**A2. Two `SECURITY DEFINER` SQL functions** in the same migration (RLS bypass for anonymous
reads, pattern from `resolve_workspace`):
- `share_agent_name(p_token text) RETURNS text` — the agent's name if the token exists and
  `revoked_at IS NULL`, else NULL. Never returns the spec. Powers `GET /share/{token}`.
- `claim_share_run(p_token text) RETURNS TABLE(status text, workspace_id uuid, graph_spec jsonb)`
  — the **atomic cap gate**: a single conditional `UPDATE share_link SET run_count = run_count+1
  WHERE token = p_token AND revoked_at IS NULL AND (run_cap IS NULL OR run_count < run_cap)
  RETURNING …`. If a row updated ⇒ `status='ok'` + the agent's `workspace_id` + `graph_spec`.
  If not, a follow-up `SELECT` categorizes `not_found` / `revoked` / `cap` (for messaging only —
  the UPDATE is the race-free gate; two concurrent runs can't both pass the cap).

**A3. Mint/list/revoke in `routers/agents.py`** (authenticated, `tenant` dep, RLS-scoped):
- `POST /agents/{id}/share` (`ShareCreate{run_cap?: int}`) → `_get_owned` the agent, INSERT a
  `share_link` with `token = secrets.token_urlsafe(16)` (128-bit), return `ShareInfo{token,
  run_cap, run_count, created_at, revoked_at}`.
- `GET /agents/{id}/shares` → list the agent's links (RLS-scoped).
- `DELETE /agents/{id}/share/{token}` → set `revoked_at = now()` (idempotent).
- Schemas `ShareCreate`, `ShareInfo` in `schemas.py`. PostHog `share_created`.

**Gates (PR-1):** pytest — mint returns a token; list shows it; revoke sets `revoked_at`; the
SQL functions resolve/deny correctly (seeded rows: ok / revoked / cap-exceeded / unknown);
tenant isolation (workspace B can't mint/list/revoke workspace A's shares). ruff + all
Playwright green. No web change yet.

## 3. Phase B — public token run endpoint + metering + cap (PR-2: the anonymous surface)

**B1. New `routers/share.py`** — **no workspace dependency** (public by design):
- `GET /share/{token}` → `{"agent_name": share_agent_name(token)}` or **404** if NULL. Never
  the spec.
- `POST /share/{token}/runs` (`ShareRunRequest{message: str, thread_id?: str}`) → call
  `claim_share_run(token)`. On `status != "ok"` yield the SSE error envelope
  (`revoked`→"This link was revoked", `cap`→"This link has reached its run limit",
  `not_found`→404-style error) + `[DONE]`. On `ok`: `GraphSpec.model_validate(graph_spec)` →
  `run_stream(graph, context_for(graph), req.message, thread_id=namespaced,
  checkpointer=engine.checkpointer)`, streaming byte-identically to `/runs`. Thread is
  **namespaced** `f"share:{token}:{req.thread_id or uuid4()}"` so anonymous visitors can't
  collide on or resume each other's threads.
- Register the router in `main.py`.

**B2. Meter as `source="share"`** — same `RunRecorder` wrapper as `/runs`, off-loop via
`asyncio.to_thread`: `RunRecorder.start(workspace_id, source="share", agent_id=…,
thread_id=namespaced)`, `.add_usage()` per usage event, `.finish()/.fail()`. `workspace_id`
comes from `claim_share_run` (the owner's workspace — cost attributes to them). PostHog
`share_run`.

**B3. Spend guards.** The per-link `run_cap` is the primary bound (A2, atomic). The Week-2
platform kill-switch (`spend.over_spend_cap()`) is checked first, exactly as in `/runs`, so
anonymous share traffic can't blow past the monthly cap.

**Gates (PR-2):** pytest — a fake-model share run streams + `[DONE]` and writes a `run` row with
`source="share"` + the owner's `workspace_id`; **the `GET /share/{token}` response body never
contains `graph_spec`/`nodes`/`edges`** (explicit assertion); cap trips (seed `run_count =
run_cap` → next run refused); revoked link refused; unknown token 404. DB-down ⇒ share run still
streams (recorder self-disables) — but note the cap gate needs the DB, so DB-down share runs are
uncapped (acceptable: platform kill-switch is the backstop; call this out in review). All e2e
green. Prod verify: mint a link via API, `POST /share/{token}/runs` with a fake graph, see the
row in Neon.

## 4. Phase C — public web page + Share button (PR-3: the UX)

**C1. Public proxies (no auth forwarded):**
- `apps/web/src/app/api/s/[token]/route.ts` → GET → API `/share/{token}` (name only).
- `apps/web/src/app/api/s/[token]/runs/route.ts` → POST → API `/share/{token}/runs`, SSE
  passthrough (copy `/api/runs/route.ts` **minus** `internalHeaders()` — these are public).

**C2. Public page** `apps/web/src/app/s/[token]/page.tsx` — fetch the agent name (404 → a
"link unavailable" state), render `Playground` in a **view+run-only** mode: no canvas, no
save/edit/Code affordances, just prompt → streamed reply. Reuse `Playground.tsx` behind a new
`shareToken?: string` prop that swaps the run call.

**C3. Web run helper + Share button:**
- `api.ts`: `runShare(token, message, threadId)` → `streamSSE(\`/api/s/${token}/runs\`,
  {message, thread_id}, onError)`.
- `Playground.tsx`: when `shareToken` is set, call `runShare` instead of `runAgent`; hide
  owner-only UI.
- **Share button** in the canvas top bar (only when the agent is saved, i.e. has an id):
  `POST /api/agents/{id}/share` → show the `/s/{token}` URL with copy-to-clipboard + a link to
  manage/revoke. PostHog `share_created` (client).

**Gates (PR-3):** Playwright `phase7-share.spec.ts` — sign in → create+save agent → Share →
copy URL → open `/s/{token}` in a **logged-out** context → streamed reply; revoke → reopening
the link shows "unavailable" / run refused; cap → error after the Nth run. `pnpm typecheck` +
ruff + full pytest green. Prod verify on www.calypr.co: create → share → open the link in a
private window → streamed reply; revoke works.

## 5. What could break — and the specific mitigation

| Risk | Mitigation |
|---|---|
| **GraphSpec leaks to anonymous users** (the core promise) | Public endpoints return name + run output only; `graph_spec` loaded server-side in the run handler; explicit e2e assertion that `GET /share/{token}` has no `graph_spec`/`nodes`/`edges`. |
| RLS blocks anonymous token lookup | `SECURITY DEFINER` `share_agent_name` / `claim_share_run` (pattern from `resolve_workspace`), not owner-privilege reliance. |
| **Public route 401s in prod** (the Week-2 #5 trap) | Share API endpoints have **no** workspace dep; `/api/s/*` proxies **omit** `internalHeaders()`. They're anonymous by construction — nothing to forward. |
| Cap bypassed under concurrent runs | The cap is a single conditional `UPDATE … WHERE run_count < run_cap RETURNING` (row-locked) — not check-then-update. |
| Anonymous runs cost real model spend | Per-link `run_cap` (default a small N, e.g. 25) + the Week-2 platform kill-switch as the global firewall. Share cost attributes to the owner's workspace. |
| Anonymous visitors collide on / resume threads | Thread id namespaced `share:{token}:{client-or-random}`; visitors can't address another's thread. |
| Metering breaks the share stream | Reuses best-effort `RunRecorder` (self-disables on DB error); stream already delivered before flush. |
| Token guessing | `secrets.token_urlsafe(16)` = 128 bits; unique-indexed; revocable. |
| Migration on populated Neon | `share_link` is a new table (additive) + two new functions; Railway `preDeployCommand` runs `alembic upgrade head`; test `upgrade head` on empty + populated DBs; tested `downgrade`. |

## 6. Rollout sequence

1. **PR-1 (Phase A)** — schema + `SECURITY DEFINER` functions + authenticated mint/list/revoke.
   Merge → Railway auto-migrates → verify mint/list/revoke + tenant isolation in prod.
2. **PR-2 (Phase B)** — public `share.py` (GET name, POST runs) + `source="share"` metering +
   cap. Merge → deploy → mint a link, run it via API, confirm the `run` row + no-spec-leak.
3. **PR-3 (Phase C)** — web `/s/[token]` page + proxies + Share button + e2e. Merge → Vercel +
   Railway deploy → create→share→open-logged-out→streamed reply on www.calypr.co.

Each PR: full pytest + all Playwright + ruff + web typecheck green before merge; squash-merge ⇒
one-commit revert. **Post-deploy prod verification is mandatory** (Week-2 taught us CI-green ≠
prod-correct — the `/runs` 401 and the checkpointer staleness only surfaced live).

## 7. Non-goals (deliberately excluded)

Per-run auth / capturing anonymous emails (later growth surface); share analytics dashboards;
editable shared copies / "fork this agent" (Month-2+); public per-agent API beyond links
(Month-3 non-goal); rate-limiting per IP (rely on `run_cap` + platform cap for the MVP);
password-protected or expiring links (add `expires_at` later if a partner asks — the column is
a trivial follow-on).
