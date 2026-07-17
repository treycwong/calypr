# Calypr — TODO

Outstanding work, roughly in priority order. Shipped phases are summarised at the bottom for
context. The visual canvas → LangGraph compile → ownable-Python round-trip is built through
Phase 5 (control flow, tools, Reflexion, RAG); what remains is mostly **getting the backend to
production** and the **RAG ingestion** next pass.

## 🟢 Image + Voice (TTS) blocks — DONE (2026-07-18), merged + live in prod

New media node type, generalized to two blocks + shared plumbing. Merged via PR #18 (squash,
`b0342d5`) — Vercel + Railway both auto-deployed clean (no build/runtime errors; `/templates`
verified end-to-end through `www.calypr.co` in prod).

- [x] **Image node** (`packages/nodes/src/calypr_nodes/image.py`) — prompt → image via OpenAI,
  defaults to **`gpt-image-2`** (real, billed — needs `OPENAI_API_KEY`); gpt-image-1/-1-mini/1.5
  and a keyless `fake` preview also selectable. `style` field lets a block be specialized (e.g.
  always-anime) without an extra Agent node.
- [x] **Voice/TTS node** (`packages/nodes/src/calypr_nodes/tts.py`) — text → speech via OpenAI,
  defaults to **`gpt-4o-mini-tts`** (real, billed); tts-1/-hd and `fake` also selectable.
  `instructions` field steers tone/pacing. Metered by input character count (API returns no token
  usage).
- [x] **Templates now default to real models** (2026-07-18): the "Image generation" and "Text to
  speech" starters use `gpt-image-2`/`gpt-4o-mini-tts` out of the box (switch to `fake` for a
  keyless preview). To keep CI offline/free despite this, `NodeContext` gained injectable
  `image_model`/`tts_model` fields (mirrors the existing chat-model seam) + `image_model_for_node`/
  `tts_model_for_node` resolvers; the starter-matrix test injects Fake clients regardless of each
  template's configured model.
- [x] **Shared plumbing**: `calypr_storage` package (Vercel Blob upload, `data:` URI fallback when
  `BLOB_READ_WRITE_TOKEN` unset) + `packages/nodes/src/calypr_nodes/_assets.py::store_asset`
  (used by both nodes). `services/model` gained `image_client.py` / `tts_client.py` +
  `image_model_for` / `tts_model_for` factories, each with a keyless `Fake*Client` for CI.
- [x] **Pricing**: `apps/api/src/calypr_api/pricing.py` — gpt-image-* (per-1M image-output tokens)
  and tts-1/-1-hd/gpt-4o-mini-tts (per-1M characters, proxied through `input_tokens`). Rates are
  best-effort — **verify against OpenAI's live price page** before trusting margins (open item).
- [x] **Rendering**: `apps/web/src/components/Markdown.tsx` gained image (`![alt](url)`) and audio
  (`[label](audio-url)`) inline rules. New `ChatImage.tsx` (image + download) and `ChatAudio.tsx`
  (slim inline pill player — play/pause, scrubber, time, download). Both nodes emit **single-line**
  captions (multi-line breaks the line-based Markdown parser — hit and fixed pre-merge).
- [x] **Provision `BLOB_READ_WRITE_TOKEN`** (2026-07-18) — Vercel Blob store `calypr-media`
  (public, Portland/PDX1, base URL `https://pr7homsjyvqypjew.public.blob.vercel-storage.com`)
  created; token set in Railway `calypr-api` + redeployed. Verified in prod: Image + Voice runs on
  the playground now return real blob URLs (not `data:` URIs).
- [ ] **Blob lifecycle / garbage collection — NOT built.** Every generation writes a permanent
  object (`runs/{png,mp3}/<uuid>.<ext>`); nothing ever deletes them — not on run/agent/share-link
  deletion, and there's no TTL. Files (and Vercel Blob storage cost) accumulate indefinitely and
  orphan on delete. Needs a cleanup story: e.g. delete blobs when their run/agent is deleted
  (`calypr_storage` would grow a `delete_blob`), and/or a periodic sweep of unreferenced objects.
- [ ] **Verify gpt-image-2 / tts-1 / gpt-4o-mini-tts pricing** against OpenAI's current price page
  — `gpt-image-1` is already legacy/dropped from the page; rates were set fail-safe-high but
  unconfirmed.
- [ ] Fast-follow (not started): vision loopback (LLM *sees* a generated image), speech-to-text
  input node, and deciding whether an intermediate node's streamed tokens (e.g. Agent output that
  only feeds a downstream Voice node) should be suppressed from the visible transcript.

## 🟢 Security — DONE (2026-07-07)

- [x] **New OpenAI key issued** and in use (Railway `OPENAI_API_KEY` ← `.env`).
- [x] **Stale Vercel `OPENAI_API_KEY` deleted** (the web never read it; the backend holds the key).
- [x] **Old exposed key revoked** in the OpenAI dashboard.

## 🔴 Open loose ends (surfaced 2026-07-12) — address before/with Week 4

- [ ] **Rotate the Neon prod DB credential** — the pooler `DATABASE_URL` (with password) lives in
  the repo-root `.env` and surfaced in a debug session. Rotate in Neon; confirm `.env` is
  gitignored; update the Railway/Vercel copies on rotation.
- [ ] **Vercel PREVIEW builds fail** (`Resource provisioning failed`) while **production** builds
  succeed — a preview-env/account issue, not code (usage is far under limits). PR preview URLs
  don't build until resolved (ping Vercel support: "prod deploys succeed, previews fail at
  provisioning"). Not blocking prod shipping — merge → production build works.
- [x] **Friendlier run-error surfacing** — DONE (Week 4 PR #12, `a6d76d7`). `run_stream` catches
  `GraphRecursionError` → `RunError` (clean copy); `run_error_message` maps exceptions (RunError →
  verbatim, CompileError → first issue, else → generic) so raw `str(exc)` never reaches clients.

## 🟢 Better Auth hosted dashboard (dash plugin) — DONE (2026-07-15)

Live on main (PR #15 `c8aca59`). `@better-auth/infra` + `dash()` wired into
`apps/web/src/lib/auth-server.ts` (after `nextCookies()` stays last); reads `BETTER_AUTH_API_KEY`
from the deployed env. Prod verified: `www.calypr.co/api/auth/dash/config` → 401 (routes live,
key-gated); `get-session` → 200.

- [x] Pinned `zod@4.4.3` as a direct `apps/web` dep — `@better-auth/infra`/`better-call`
  peer-require zod v4 (`dash()` calls `z.url()`); a stray transitive zod 3.25.76 was 500'ing
  every `/api/auth/*` route. App imports zod nowhere directly, so blast radius = the auth stack.
- [x] Dashboard base URL must be `https://www.calypr.co/api/auth` — the apex `calypr.co` has **no
  DNS** and doesn't resolve. (User set it; connection now works.)
- Local-dev note (today): the API reads `CALYPR_DATABASE_URL` (default `localhost:5432`); creating
  agents locally needs `docker compose -f infra/docker/compose.yaml up -d` (pgvector) — not the
  Neon prod DB. `apps/web/.env.example`'s `DATABASE_URL` is correct (Better Auth's own `pg` Pool),
  not drift.

## 🟢 Partner-readiness polish (MVP Week 4) — DONE (2026-07-13)

Live in prod. Plan: `WEEK4-PARTNER-READINESS-PLAN.md`.

- [x] **PR-1 — friendly, leak-safe run errors** (#12, `a6d76d7`): recursion guard + tiered
  `run_error_message` in `runs.py`/`share.py`.
- [x] **PR-2 — web error boundaries + toasts** (#13, `555d146`): dependency-free `ToastProvider`
  (`components/ui/toast.tsx`) + App-Router `error.tsx`/`global-error.tsx` boundaries, wired to
  failed saves/agent-loads/share-mints and run errors. `phase11-polish.spec.ts`.
- Deferred (non-eng): the extra template (only if a partner gap appears) and the **blind
  code-review panel** (Month-1 gate deciding Month-2 codegen-quality buffer).

## 🟢 Production deployment — DONE (2026-06-26)

Live: **www.calypr.co** (Vercel) → proxies to **https://calypr-api-production.up.railway.app**
(Railway) → **Neon** Postgres (pgvector). `/api/templates` verified end-to-end in prod.

- [x] **FastAPI engine on Railway** — `apps/api/Dockerfile` (uv workspace) + `railway.json`
  (Alembic `upgrade head` on preDeploy, `/health` check). `CALYPR_API_URL` set in Vercel.
  `/health`, `/readyz` (db ok), `/templates` all green. Project: `calypr-api`.
- [x] **Railway ↔ GitHub auto-deploy** — service connected to `treycwong/calypr` @ `main`;
  pushes now redeploy the backend automatically (verified with a healthy GitHub-sourced build).
  Both web (Vercel) and backend (Railway) are now hands-off on `git push`.
- [x] **Neon Postgres** via Vercel Marketplace (`DATABASE_URL`, Sensitive). Alembic schema +
  Better Auth tables migrated; `CREATE EXTENSION vector` applied. Engine made pgBouncer-safe
  (`prepare_threshold=None`). Removed a stale `DATABASE_URL` + 14 dead env vars from a prior app.
- [x] **Better Auth activated** — `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL=https://www.calypr.co`,
  `GITHUB_CLIENT_ID/SECRET` set; GitHub OAuth app callback `…/api/auth/callback/github`.
  `/api/auth/get-session` returns 200. **Last check (you):** click "Sign in with GitHub" on
  www.calypr.co and confirm it lands on the dashboard.
- [ ] **Preview-env `CALYPR_API_URL`** not set (needs interactive branch pick; low priority —
  preview auth wouldn't match the prod OAuth callback anyway).

## 🟡 RAG — next pass (create your own vector DB)

The Knowledge block + keyless demo KB shipped; pointing it at real data is the ingestion pipeline.
**Phased plan: `RAG-INGESTION-PLAN.md`** (Phase 6a–6e; build order 6a → 6e).

- [ ] **6a** — Alembic migration: **`knowledge_base` + `kb_chunk`** tables (pgvector embedding
  column, RLS by `workspace_id`, mirroring the existing tenant isolation) + an **embeddings seam**
  (`fake` | `openai`) mirroring `model_for` in `services/model` (keyless demo, real prod).
- [ ] **6b** — API: **`POST /knowledge-bases`** + an upload → chunk → embed → store pipeline.
- [ ] **6c** — Wire the Knowledge node's **`pgvector` source** to a real KB collection at runtime
  (it's codegen-only today).
- [ ] **6d** — Web: a **Knowledge area** to create KBs + upload documents (+ KB dropdown in the
  Knowledge node config).
- [ ] **6e** — Tests: pytest (RLS + ingest + `embed_for`) · API · keyless Playwright.

## 🟣 Dynamic fan-out — LangGraph `Send` (orchestrator decides N workers at runtime)

The shipped Orchestrator–Worker template (**Trip itinerary planner**) is **static** — a fixed set
of workers wired on the canvas. The dynamic version (the reference's slides 2–4: `Send` +
`WorkerState`) lets the orchestrator spawn **N parallel workers at runtime, one per subtask** — the
classic "one worker per item" / map-reduce pattern (e.g. summarize N documents). It needs a new
engine primitive (it changes the compiler's edge model: an edge can expand into a *variable* number
of parallel branches at runtime).

- [ ] **`Send` in the DSL/compiler** — let a node's routing return `list[Send("worker", payload)]`
  instead of a single branch name; teach `compile.py` + `generate.py` to wire it (today `routing()`
  returns one `str`).
- [ ] **Orchestrator node** — splits the input into N subtasks at runtime and emits one `Send` per
  task, paired with a single reusable **Worker** node (reused N times, not N drawn boxes).
- [ ] **`WorkerState`** — a per-worker sub-state (the task payload), separate from the main graph
  state; results aggregate back through an append-reducer channel (as the static version does).
- [ ] Round-trip codegen + a dynamic template, keyless/deterministic with the fake model.

## 🟢 CI / maintenance — DONE (2026-07-07)

- [x] **Bumped GitHub Actions off Node 20**: `actions/checkout@v7`, `actions/setup-node@v6`,
  `astral-sh/setup-uv@v8.3.1` (no floating `v8` tag — pinned), `pnpm/action-setup@v6`.

## 🟢 Usage persistence + durable checkpointing (MVP Week 2) — DONE (2026-07-08)

Live in prod (PRs #3–#7). See `WEEK2-USAGE-PERSISTENCE-PLAN.md`.

- [x] **Usage enrichment + pricing** (#3) — `node_id`+`model` on usage events; `pricing.py`
  (`cost_usd`, fail-closed on unknown models, `fake`=$0).
- [x] **`run` / `run_usage` schema + `RunRecorder`** (#4) — migration `0004_runs` (RLS), best-
  effort recorder (self-disables if DB down), wired into `/runs` (`source="playground"`) +
  `/assist` (`source="assist"`). **The AI assistant is now metered.**
- [x] **`/runs` kept public** (#5, hotfix) — lenient `run_workspace` dep never 401s; web
  `/api/runs` proxy forwards `internalHeaders()`. (PR #4 had briefly 401'd the prod playground.)
- [x] **Durable Postgres checkpointer + spend kill-switch** (#6) — FastAPI lifespan swaps in the
  durable saver (threads survive Railway restarts; falls back to in-memory on any failure);
  `CALYPR_PLATFORM_SPEND_CAP_USD` monthly loss firewall.
- [x] **Checkpointer connection pool** (#7, hotfix) — replaced the single `from_conn_string`
  connection (went stale on Neon idle → "connection is closed") with a health-checked
  `AsyncConnectionPool`. Verified in prod after a 5-min idle.
- **New Railway env:** `CALYPR_CHECKPOINT_DATABASE_URL` (Neon **direct**/non-pooler endpoint),
  `CALYPR_PLATFORM_SPEND_CAP_USD`.

### Follow-ups from Week 2 (not blocking)

- [x] **Checkpointer observability** — `/readyz` now reports `checkpointer: postgres|memory` so
  durable-vs-fallback is queryable without reading INFO logs.
- [ ] **Force RLS on `run`/`run_usage`** — today isolation is app-level `workspace_id` filtering
  (RLS enabled but not FORCEd, app role owns the tables). When forcing, give the spend-cap's
  platform-wide `SUM(cost_usd)` query a bypass path (it relies on the owner seeing all rows).
- [ ] **Re-verify non-Anthropic prices in `pricing.py`** against provider pages before billing
  (Month-3 credits); rates are hand-entered and flagged in-file.

## 🟢 Share-to-test links (MVP Week 3) — DONE (2026-07-12)

Live in prod (PR #9 `570f250`). Full plan: **`WEEK3-SHARE-LINKS-PLAN.md`**. Owner mints an
unguessable `/s/{token}` link → anyone runs the agent logged-out, streamed, **never receiving the
GraphSpec**, capped per link (default 25), metered `source="share"`.

- [x] **PR-1** — `0005_share_links` (`share_link` table + RLS) + `SECURITY DEFINER`
  `share_agent_name` / `claim_share_run` (atomic cap gate) + authenticated mint/list/revoke in
  `routers/agents.py`.
- [x] **PR-2** — public `routers/share.py`: `GET /share/{token}` (name only) +
  `POST /share/{token}/runs` (loads spec server-side, streams via `run_stream`, meters
  `source="share"`, enforces cap). **No workspace dep** (public by design).
- [x] **PR-3** — web `/s/[token]` page + **public** `/api/s/*` proxies (no `internalHeaders`) +
  authed `/api/agents/[id]/share*` proxies + Share button + `phase10-share.spec.ts`.
- [x] **UI polish** — Share popover w/ copy-link (`81fe634`); redesigned `/s` page (interactive
  ASCII field + glass chat, mobile-first, `eb02793`); ASCII agent-graph hero backdrop (`6ed4fe4`);
  **markdown rendering** in the shared chat + Try-it playground (PR #11 `471b303`).
- [x] **Bug fix — unbounded graph cycles** (PR #10 `3ab2354`): a saved agent with a back-edge
  into the Agent looped to the recursion limit (~25 model calls + a wall of text before erroring).
  `validate_graph` now rejects all-unconditional cycles *before any model call*, naming the loop.

## 🟢 Reverse round-trip parser (MVP Week 5 — Month 2 kickoff) — DONE (2026-07-15)

Live on main (PR #14 `c2d66ee`). Plan: `WEEK5-ROUNDTRIP-PARSER-PLAN.md`. New `services/roundtrip`
package: `parse_python(code) -> ParseResult(spec, warnings, degraded_nodes)` — topology + State
walkers over the closed `build_graph()` grammar, plus the `# calypr: {…}` metadata trailer in
`generate.py`. Node-config recognizers are Week 6.

- [x] **PR-1** — scaffold `services/roundtrip` + topology walker (`add_node`/`add_edge`/
  `add_conditional_edges` incl. ReAct `tools_condition`); every node degrades to a `code` node
  placeholder. Gate met: topology round-trips for `golden.py` + all 14 STARTERS.
- [x] **PR-2** — State-class walker (reducers ↔ `add_messages`/`operator.add`) + metadata
  trailer emit/consume (deletion-safe → auto-layout). Gate met: equivalence-modulo-layout over
  all STARTERS; trailer-stripped copy still parses. (225 passed, ruff clean, CI green.)
  - Finding baked into the equivalence relation: ReAct `tools_condition` edge *labels* are not
    recoverable (LangGraph prebuilt discards them) — behaviourally lossless; topology + Router
    conditions do round-trip.
- [ ] **In parallel (non-eng):** run the blind code panel — <70% would-merge redirects Month 2
  to codegen quality (standing kill condition). **Still open.**
- [ ] **Next: Week 6** — per-node config `parse()` recognizers in `packages/nodes` so nodes stop
  degrading to Custom Code; registry-wide property test `parse(generate(spec)).spec == spec`.

### Alt/parallel Week-5 track — internal codegen-quality harness — NOT STARTED (parser chosen)

Plan: `WEEK5-CODEGEN-EVAL-HARNESS-PLAN.md`. Deferred — Week 5 went to the round-trip parser; this
harness was not built. Still a valid parallel/next option. We can't outsource the blind panel right now, so
build an automated gate to test generated code continuously (complements, does **not** replace,
the human panel — which stays the absolute ≥70% bar). Reuses the existing corpus/execution in
`test_templates.py` + `_import_generated`. Recommendation: run Layers 1–2 **in parallel** with
the round-trip parser; make it the sole Week-5 focus only if a first run scores codegen poorly.

- [ ] **Layer 1 (PR-1)** — mechanical gate in `services/codegen/tests/test_quality.py`:
  ruff format/lint clean, type-check passes, imports+`build_graph().invoke()` run on fake model,
  no `calypr_*` deps in generated code. Deterministic, keyless, runs in existing CI.
- [ ] **Layer 2 (PR-2)** — `services/codeeval`: blind LLM-as-judge (`Verdict(would_merge,
  confidence, scores)`), pairwise vs hand-written references, cross-family judge via `model_for`,
  per-template report. Keyless-skip; `CALYPR_CODEEVAL_MODEL` for keyed nightly runs.
- [ ] **Layer 3** — calibrate harness verdicts against a minimal human review; track score over
  time to catch codegen regressions.

## 🟢 Blog — tutorials + product updates (MDX-in-repo) — DONE (2026-07-16)

Live: **www.calypr.co/blog** (PRs #16 `83fa693`, #17 `8009af2`). Plan: `BLOG-MDX-PLAN.md`.
No CMS — posts are `.mdx` in `apps/web/src/content/blog` exporting a `metadata` object
(git is the CMS; publishing = merging a PR). Add posts there to publish.

- [x] **PR-1** — `@next/mdx` + `remark-gfm` + `rehype-pretty-code` (shiki `min-dark`,
  string-form plugins for Turbopack); landing header/footer extracted to `components/site/`;
  static `/blog` index (client filter chips) + SSG `[slug]` pages; `.prose-blog` typography on
  the monochrome tokens; 2 seed posts (RAG tutorial + Weeks 1–5 changelog). e2e 29/29.
- [x] **PR-2** — `sitemap.ts` (from the same content source), `robots.ts` (disallows `/api/`,
  `/dashboard`, `/sign-in`, `/s/` — share links stay unlisted), `metadataBase` + per-post
  canonical/article OG/Twitter. Prod-verified: sitemap 4 urls, robots rules, OG tags live.
- [x] **Authoring guide** — `apps/web/src/content/blog/README.md`: step-by-step reference for
  writing/publishing a post (metadata fields, MDX gotchas, local preview, shipping via PR, prod
  verification one-liners). Not a page route — lives with the content for future reference.

## 🔵 Optional follow-ups

- [ ] **RAG-as-tool** — agentic retrieval exposed as a tool over the existing Tool node + loop
  (vs. the current retrieve-then-generate), for when the agent should decide *when* to retrieve.
- [ ] **Chroma provider** in `knowledge_catalog.py` — a second codegen source alongside pgvector.
- [ ] **State editor** for custom channels on the canvas (today it uses a fixed `DEFAULT_STATE`;
  the engine already unions node-declared channels, so this is UX, not correctness).
- [ ] **Durable/global assist daily cap** — assist calls are now metered as `run_usage` rows
  (`source="assist"`, shipped Week 2), but `CALYPR_ASSIST_DAILY_CAP` is still an **in-memory,
  per-process** counter (resets on restart, not shared across instances). Back it with the DB
  (or an OpenAI account budget cap meanwhile). The platform-wide `CALYPR_PLATFORM_SPEND_CAP_USD`
  kill-switch is the durable loss firewall in the interim.

---

## ✅ Shipped (Phases 0–5)

- **Phase 0–2** — monorepo, FastAPI engine, DSL + codegen + drift check, Postgres + pgvector +
  Alembic baseline, Next.js canvas (palette / nodes / config / save), playground streaming, CI.
- **Phase 3** — per-node `codegen()` → ownable LangGraph Python, `/codegen` + web Code view, the
  Custom Code escape hatch (the "no-ceiling" round-trip).
- **Phase 4** — Router / If-Else conditional control flow, the agent-type ladder (Russell &
  Norvig), Evaluator + Memory nodes, archetype templates.
- **Phase 5a/b** — Tool node + catalog (`demo_search` / Tavily), agent tool-binding, the ReAct
  `ToolNode` + `tools_condition` loop, Reflexion (Responder + Revisor bounded loop).
- **Frameworks vs Templates** — starters split into frameworks (agent patterns) + use-case
  templates (multi-agent pipelines: Market Research, Customer Support, Contract Review).
- **Auth + deploy** — monochrome landing page, Clerk → Better Auth (GitHub OAuth, dev fallback),
  Vercel Git integration (auto-deploys `main` → www.calypr.co).
- **Phase 5c — RAG** — Knowledge (retriever) block, `knowledge_catalog.py` (demo +
  pgvector sources), RAG framework + grounded Market Research / Customer Support templates,
  agent prompt-placeholder substitution in codegen, demo round-trip + pgvector codegen tests.
- **Phase 5d — LLM routing** — Router gains an LLM-classifier kind (writes a `task_type` channel);
  "Summarize or translate" template; the node was renamed **If-Else → Router**.
- **Phase 5e — Orchestrator–Worker (static)** — "Trip itinerary planner" template: parallel
  fan-out → workers → fan-in synthesizer via the `messages` (`add_messages`) reducer; named
  agents (an Agent `label`); **left-to-right layered canvas layout** so fan-out is visible.
- **Phase 9 — AI Assistant (prompt → canvas)** — natural-language prompt → validated `GraphSpec`
  via `services/assistant` (`calypr_assistant`: registry-derived prompt, validate→repair loop,
  keyless `fake` path) → `/assist` SSE → panel that previews the graph live on the canvas with
  Apply / Discard / Undo. Kimi/DeepSeek/OpenAI routing via `CALYPR_ASSISTANT_MODEL` (unset ⇒
  fake). Live on www.calypr.co (Railway `gpt-4o-mini`). PR #1 (`1aa6d28`).
- **MVP Week 1 — Analytics** — PostHog wired client (`posthog-js`, ceiling events
  `code_view_opened/copied/downloaded`, run/template/assistant events) and server
  (`posthog` Python client + ASGI context middleware; `graph_compiled`, `agent_created/
  updated/deleted`, `agent_run_*`, `assist_requested`, `assist_daily_cap_reached`). Env-gated
  no-op when keyless (dev/CI). See `METERING-ANALYTICS-PLAN.md`. PR #2 (`b8e0824`).
