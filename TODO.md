# Calypr — TODO

> **Everything currently open, in priority order.** Sections below this one are the historical
> record — what shipped and why. Updated 2026-07-23.

## ⏭️ NEXT — what's actually blocking

### 1. Turn Stripe on (blocked on credentials)

The code is merged and correct; nothing works until three values exist. See
`apps/api/.env.example` for the canonical list, and the "Creating the Plus price" steps below.

- [x] **Live product exists** — "Calypr Plus", $20.00 USD/month, active:
      `price_1TwCr8Q4CLwWKY6VKVaMtiYY` (livemode). Verified read-only against the live key.
      The id first put in `.env` (`price_Uw51xN…`) did not exist in that account and was
      corrected. An earlier `sk_org_live_…` key was also replaced: **Organization API keys need
      a `Stripe-Context` header** naming the target account, which this code does not send, so
      every call 400s. Use a plain account key (`sk_test_…` / `sk_live_…`).
- [x] **TEST product + price + webhook endpoint created** —
      `price_1TwD8eQ4CLwWKY6V6GgS09bu` ("Calypr Plus (Test)", $20/mo, `livemode=False`).
- [x] **TEST values set on Railway** and deployed. `/billing/status` reports `enabled: true`.
- [x] **Loop proven end-to-end locally against real Stripe test credentials** (2026-07-23):
      `/billing/checkout` created a real `cs_test_…` session, and the webhook — signed with the
      **actual** signing secret, not a fixture — walked the whole lifecycle:
      `free` → `checkout.session.completed` → **plus** (customer mapped) → `invoice.paid` holds →
      `past_due` **keeps access** → `subscription.deleted` → **free**. 35/35 billing tests pass
      against a real database.
- [x] **Real test payment confirmed in production (2026-07-23)** — Stripe reached the deployed
      endpoint, the signature verified on the wire, and both `checkout.session.completed` and
      `invoice.paid` are recorded in `stripe_event`. `treycwong@gmail.com` is mapped to
      `cus_Uw5V71aLHnaox9`.
- [ ] **Cancellation is unproven *in production*.** It works locally, but the paid account was
      already `plus` (set by hand earlier), so neither `free → plus` nor `plus → free` was
      actually *observed* end-to-end on the deployed endpoint. Cancel the test subscription in
      the Stripe dashboard and watch the plan return to `free` — that closes the last gap, and
      the downgrade path is the one where a bug costs a paying customer their access.
- [ ] **Go live** — swap in the live values (live price is
      `price_1TwCr8Q4CLwWKY6VKVaMtiYY`) plus a **separate live webhook signing secret**. Keep
      live values on Railway only, never in `.env`.
- ⚠️ **`.env` had both TEST and LIVE blocks active**, and since later definitions win, the
      **live** keys were what actually loaded — it looked test-configured and wasn't. The live
      block is now commented out. Worth re-checking whenever those keys are touched.
- [ ] **Point the webhook** at `https://calypr-api-production.up.railway.app/billing/webhook`
      — Railway directly, *not* calypr.co: signature verification needs the exact raw bytes, and
      the signing secret belongs where the DB is. Events: `checkout.session.completed`,
      `customer.subscription.{created,updated,deleted}`, `invoice.paid`, `invoice.payment_failed`.
- [ ] **Test the loop end-to-end** on the `tracey@theflowops.com` free workspace: pay in test
      mode → confirm `plus` → cancel → confirm `free`. **Go through the actual button** — a
      payment made in the Stripe dashboard carries no `client_reference_id`, so it correctly
      does nothing, which looks like a bug if you weren't expecting it.
- ⚠️ **Local dev picks up whatever is in the repo-root `.env`** (`config.py` calls
  `load_dotenv` on it). With live keys sitting there, running the API locally creates **real**
  Stripe Checkout Sessions — no charge, but real objects in the live account. Keeping *test*
  keys in `.env` and live keys only on Railway removes the hazard entirely.

#### Creating the Plus price (Stripe dashboard)

1. Toggle to **Test mode** (top-right). Test and live have entirely separate products, keys,
   endpoints and signing secrets — a price id from one is meaningless in the other.
2. **Product catalogue → Add product**.
3. Name it `Calypr Plus`. The description is customer-visible on the Checkout page.
4. Pricing: **Recurring**, **$20.00 USD**, billing period **Monthly**. Leave the default
   "flat rate" / per-unit — our Checkout Session sends `quantity: 1`.
5. Save, then open the product and copy the **price** id — it starts `price_…`, *not*
   `prod_…`. `prod_` is the product; Checkout needs the price.
6. Repeat in **live mode** when you're ready to charge real money, and set the live
   `STRIPE_PLUS_PRICE_ID` + `sk_live_…` + a *separate* live webhook signing secret.

Or with the Stripe CLI, if you prefer it reproducible:

```bash
stripe products create --name="Calypr Plus"
stripe prices create --product=prod_XXX --unit-amount=2000 --currency=usd -d "recurring[interval]=month"
```

### 2. Credit ledger + enforcement (the other half of billing)

`0013` shipped the *entitlement* half: paying flips the plan. Credits are **computed**
(`pricing.credits_for`) but nothing debits them, so the 2,000/month grant isn't enforced and a
Plus user currently has no ceiling beyond `CALYPR_PLATFORM_SPEND_CAP_USD`.

- [ ] `credit_ledger` table (PRICING-SPEC §4) + monthly grant on `invoice.paid`
- [ ] Debit post-run from the accumulated usage events (same hook as `RunRecorder`)
- [ ] 402 `{reason: "credits"}` in `create_run` / `/assist` when the balance is spent
- [ ] Free-tier BYOK enforcement: Free has *no* platform node runs per the plan matrix, and
      nothing enforces that today

### 3. Before the first real charge (money safety)

- [ ] **Blob GC does not exist** — every image/TTS generation writes a permanent object under
      `runs/{png,mp3}/…`; nothing deletes them, ever, including on run/agent/share deletion. A
      monotonically growing bill under a "positive gross margin" gate. Needs `delete_blob` in
      `calypr_storage` wired to deletions + an orphan sweep.
- [ ] **FORCE RLS on `run` / `run_usage`** — isolation is app-level `workspace_id` filtering and
      billing will read these tables. Give the platform-wide `SUM(cost_usd)` spend-cap query a
      bypass path when forcing.
- [ ] **Durable assist cap** — `CALYPR_ASSIST_DAILY_CAP` is in-memory and per-process (resets on
      restart, not shared across instances). The Free tier's assist grant needs the ledger.
- [ ] **Rotate the Neon prod credential** — the pooler URL with password sits in the repo-root
      `.env` and has surfaced in a debug session. Ops task, not a PR.
- [ ] **Verify the non-Anthropic prices in `pricing.py`** against provider pages. They are the
      input to *both* margin and credits now, and the OpenAI GPT-5.6 tier came from aggregators.

### 4. Revisit the beta cohort (deferred by decision, 2026-07-23)

`beta` currently means "early access, including code export" and is granted by a one-time
invite. It needs an ending, and the mechanics now support one (`waitlist.granted_at` makes a
demotion stick — before that fix, demoting the cohort would have silently undone itself).

- [ ] **Decide what `beta` becomes** when the beta ends: convert to paid Plus, drop to Free with
      a grace period, or keep as a permanent comped tier for early partners.
- [ ] **Decide whether `beta` should keep code export** once Plus is on sale — right now it's
      the same entitlement for free, which is fine for ~10 partners and not fine at scale.
- [ ] Whatever the answer: it's a bulk plan change plus a comms email, not a code change.

### 5. Product decisions still open

- [ ] **Read-only code viewing** — the Code tab shows a 14-line preview to Free today, and the
      full file to `beta`/`plus`. Decide before Plus goes on sale whether *viewing* is free (it
      doubles as the "no lock-in" reassurance that sells the plan) or paid.
- [ ] **Acquisition has no plan.** Cancelling the OSS launch removed the roadmap's only
      top-of-funnel (Show HN). The blog is shipped, indexed and has two posts — making it a
      deliberate channel is the cheap replacement, but somebody has to decide that.
- [ ] **Month-1 code-quality gate never ran** (≥70% would-merge, blind panel). Chosen
      substitute — the automated harness in `WEEK5-CODEGEN-EVAL-HARNESS-PLAN.md` Layers 1–2 —
      is also not built. It's a standing kill condition on everything downstream.

### 6. Known defects (not blocking, but real)

- [ ] **Generated Python collapses multi-Tool dispatch.** The runtime was fixed in PR #41
      (`ctx.tool_owners`); `services/codegen/generate.py:214` still emits one `tools_condition`
      branch, so an agent wired to two Tool nodes exports code that reaches only one of them.
      **Must be fixed before any Plus customer exports** — they'd get code that behaves
      differently from their canvas. Parser must change in step (it discriminates Router vs
      ReAct by the routing function's name).
- [ ] **Five config fields the engine never reads** (found by the 2c audit) — implement or
      delete: `agent.max_steps`, `agent.utility_criteria`, `input.mode`, `output.stream`,
      `tool.http_method`. The last is a real product gap: "call any JSON API" can't POST.
- [ ] **`e2e/tests/phase-assistant-model.spec.ts:166` is environment-sensitive** — passes in CI
      and on a machine with no `.env`, fails identically on unmodified `main` when real provider
      keys are present (it asserts `.last()`, which becomes a real model answer). Pre-existing.
- [ ] **Neon preview branches** — nothing auto-deletes a preview's branch when its PR closes, so
      the limit that broke Vercel Previews for weeks will be hit again. Check the Neon–Vercel
      integration for an auto-cleanup setting.
- [ ] **Saved-agent count** — 21 agents exist in prod, all repaired by `0011`. Worth a look
      before launch to confirm none are half-built experiments a new user could stumble into.
- [ ] **The prod smoke proves "answers", not "used its tools".** An anonymous run carries no
      connector or workspace key, so `tpl-mcp-react` / `tpl-notion-assistant` /
      `tpl-image-finder` passed on the model's own knowledge without necessarily calling MCP,
      Notion or Unsplash. Tool *invocation* needs a signed-in pass with credentials attached —
      worth doing now that Notion is live.

### 7. Feature backlog (Month 4+, unchanged)

RAG ingestion (Phases 6a–6e), dynamic fan-out (`Send`), stdio MCP transport, Chroma provider,
Anthropic image blocks, RAG-as-tool, state editor for custom channels. See the sections below.

---

## 🔀 PIVOT (2026-07-22): closed product, code export is paid

The lead differentiator is no longer "your graph is yours, here's the Python." The product goes
**closed**; code export becomes a **paid** feature; the near-term bar is that the **nodes are
well connected and workable**, then pricing. Consequences, so nothing downstream reads stale:

- **Week-11 OSS launch is cancelled** — `packages/dsl`, `services/codegen`, `services/roundtrip`
  stay proprietary. `MVP-EXECUTION-PLAN.md` Week 11 and `ROADMAP-6M.md` §Month-3 still describe
  the Show HN; that was also the planned top-of-funnel, so **acquisition needs a new story**.
- **The Month-2 gate is retired** (≥50% ceiling-resolution, ≥40% 30-day retention). It measured
  the open product's thesis — do users who hit the wall drop into code and stay. Not a go/no-go
  any more; at most a feature metric.
- **Code export = `plus`** (`has_roundtrip` never graduates), enforced by
  `deps.require_code_export` on `POST /parse`, not just hidden in the UI. `beta` keeps it.
- **Deferred, not dropped:** the codegen multi-Tool dispatch collapse (below). It only affects
  *exported* code, so it moves behind the MVP — but it must be fixed **before any Plus customer
  exports**, or they get code that behaves differently from their canvas.

### Shipped in the pivot

- [x] **Code export retiered + paywalled** — `require_code_export` (402 `{reason: "plan",
  feature: "code_export"}`), `/api/parse` proxy forwards `internalHeaders()`, 4 tests incl. the
  402 and both entitled plans. Enforced only where `CALYPR_INTERNAL_KEY` is set (dev/CI/e2e all
  resolve to the shared dev workspace, which is `free`).
- [x] **Wiring matrix** (`services/compiler/tests/test_wiring_matrix.py`) — Input → A → B →
  Output for all **144 ordered pairs** of node types, configs harvested from the starters so it
  can't drift. Two invariants: **accepted ⇒ runnable** and **rejected ⇒ actionable** (a code,
  and a node/edge to highlight). Plus a meta-test that reads the validator's vocabulary out of
  its own source, so a new rule without a test fails the suite.
- [x] **Bug found by the matrix + fixed** — `routing_edge_unconditional`. `compile.py` wires a
  branch-deciding node with `add_conditional_edges` (labelled edges only) and skips it in the
  plain-edge pass, so an **unlabelled out-edge is discarded, not merely unlabelled**. A Revisor
  wired straight to Output — the obvious thing to draw — validated clean, ran, and returned
  `output: None`, with nothing anywhere to explain it.
- [x] **Few-shot regression suite** (`services/assistant/tests/test_few_shot_graphs.py`) — every
  prompt example validates, runs, and obeys the rules the prompt states. A bad few-shot doesn't
  fail, it *teaches* the mistake; that is precisely how PR #41 happened. `_anime_image` and
  `_spoken_assistant` had no coverage at all before this.

- [x] **2b — live prod smoke** (2026-07-22): all **22 starters** production serves, run against
  real models via `www.calypr.co/api/runs`. **22/22 answered.** Found the `fake`-model defect
  below, which no test could have caught.
- [x] **Bug found by 2b + fixed** — four starters shipped `model: "fake"` (the test seam that
  answers `Echo: …`): **Reflexion** (both LLM nodes — the whole reply was an echo), **Routing**
  (the classifier, so branch decisions were canned while the visible answer looked fine),
  **Utility-based** (the evaluator), **Learning** (memory summarisation). Now `gpt-4o-mini`,
  with a per-starter assertion. Invisible to CI by construction: the starter tests inject Fake
  clients regardless of configured model. **Not live until the next deploy.**
- [x] **Code preview paywall** — `/codegen` truncates to 14 lines for an unentitled workspace
  (`may_export_code`); the Code tab shows real readable code fading out, plus an Upgrade CTA;
  copy/download disabled. `code_upgrade_clicked` + `graph_codegen_requested {truncated}` give
  the tab a conversion rate.

- [x] **Model is now a workspace setting** (migration `0010`, `workspace.default_model`).
  One resolution rule — `effective_model`: node's own model → workspace default →
  `PLATFORM_DEFAULT_MODEL` (`gpt-4o-mini`). Blocks and starters ship `model: ""`, so Settings →
  Workspace decides the whole canvas and an explicit per-node choice still wins. `fake` stays
  selectable (CI/e2e/offline) but is nobody's default. Also fixed: the canvas defaulted
  **Router, Evaluator, Memory, Responder and Revisor** to `fake` — the same defect as the
  templates, for hand-built graphs.

## 🟢 Stripe billing — webhook + checkout (Week 9, part 1) — 2026-07-23

The payment → entitlement loop. `POST /billing/webhook` verifies, deduplicates and applies;
`POST /billing/checkout` hands off to Stripe Checkout; `GET /billing/status` lets the checkout
page render the truth on first paint.

- [x] **Signature verification before anything else** — the raw body is verified against the
  signing secret before it is parsed, and *before* a DB session is opened, so an unsigned POST
  (which anyone can send) costs a hash rather than a connection. 5 tests cover forged, wrong-
  secret, tampered-body and stale-timestamp; all 5 fail if verification is removed.
- [x] **Idempotency** — `stripe_event` keyed on Stripe's own `evt_…`, inserted *before* side
  effects, so the insert is the check. Stripe delivers at-least-once and these handlers are not
  naturally replay-safe: a redelivered `subscription.deleted` after a re-subscribe would
  otherwise downgrade a paying customer.
- [x] **Retry only when retrying helps** — transient failure ⇒ 500 (Stripe backs off, and the
  idempotency row is dropped so the retry gets a real attempt); permanently unmappable event
  (a customer we don't know) ⇒ 200, because three days of redelivery changes nothing.
- [x] **`past_due` keeps access.** The card failed but the subscription isn't over and Stripe is
  still retrying; cutting someone off mid-dunning turns a hiccup into churn. `unpaid`/`canceled`
  are where the entitlement ends. Unknown statuses leave the plan alone.
- [x] **`beta` is never downgraded** by a subscription event — that cohort has no subscription.
- [x] Migration `0013`: `workspace.stripe_customer_id` (unique) + `stripe_event`.
- [x] **Credit rates for Image + Voice — the "blocker" dissolved.** It was a documentation gap,
  not a pricing one: `credits_for` derives from the USD table (`cost_usd × 500`), and both were
  already priced there. Image is token-billed on image-output tokens; TTS records characters in
  `input_tokens`. A test asserts the 5× margin holds across every model in the table. At today's
  rates the 2,000-credit Plus grant buys ~125 images, ~266k characters of speech, or ~9,000 chat
  turns.

> Operational follow-ups for this section now live in **NEXT §1–§2** at the top of the file.
> Note on limits: Image/Voice deliberately have no per-run cap beyond their credit cost — a cap
> needs the ledger to mean anything, and `CALYPR_PLATFORM_SPEND_CAP_USD` is the interim firewall.

### Still open in the pivot

- [x] **Saved agents carrying `fake` — REPAIRED** (migration `0011`, 2026-07-22). Changing the
  defaults couldn't reach stored data, so an agent saved from the old Reflexion template would
  have echoed forever. Verified in production: **0 of 21 saved agents** still carry `fake` on an
  LLM node.
- [ ] **Read-only code viewing** — now a 14-line preview for Free, full file for `beta`/`plus`.
  Whether *viewing* stays free is still open → **NEXT §5**.
- [x] **2c — config-panel completeness — DONE (2026-07-22)**. Audited all 14 node types, ~90
  config fields, against what the canvas actually lets you set. Gaps closed:
  - **`agent_type` had no control at all** — `AGENT_TYPE_OPTIONS` sat in `graph.ts` with six
    written labels and nothing rendered it, so a hand-built Agent was stuck on `model_based`
    *and* the goal/reflection/utility fields in the same panel were unreachable dead UI. This
    **reverses the Phase 5a decision** ("the templates carry the type now", `5a741e1`); the test
    that pinned its absence is inverted, not deleted, so the history stays legible.
  - **`temperature` / `max_tokens`** on every LLM block, behind an "Advanced" disclosure.
  - **`reflection_criteria`** (what a reflection agent critiques against).
  - **`imports`** on Custom Code — the escape hatch could not reach the standard library.
  - **`response_format`** on Voice (also decides the clip's file extension).
  - Gate: `services/compiler/tests/test_config_panel_coverage.py` reads the panel's source and
    fails if a config field is neither editable nor explicitly justified, so adding a field now
    forces a decision. Excuses are grouped by *reason* — wiring / inert / server-resolved — and a
    separate test asserts the "wiring" escape hatch only ever holds `*_channel` names.

### Found by the 2c audit — config fields the engine never reads

Five fields are declared on config models, round-trip through the DSL, and are read by
**nothing** — a lie in the schema, since setting them has no effect. They're deliberately absent
from the config panel (a knob that does nothing is worse than no knob) and listed as
implement-or-delete in **NEXT §6**. The `INERT` set in
`services/compiler/tests/test_config_panel_coverage.py` is the enforced copy of that list.
- [ ] **2b caveat — the smoke proves "answers", not "used its tools".** An anonymous prod run
  has no connector or workspace key, so `tpl-mcp-react` / `tpl-notion-assistant` /
  `tpl-image-finder` passed on the model's own knowledge without necessarily calling MCP,
  Notion or Unsplash. Tool *invocation* still needs a signed-in run with credentials attached —
  worth a second pass now that Notion is live.
- [x] **2b re-run after deploy — DONE (2026-07-22, PR #43 `050afc9`)**: **22/22 PASS in
  production**, this time with an assertion on the *content* (a reply starting `Echo:` is now a
  FAIL, not a pass). Reflexion, Routing, Utility-based and Learning all answer for real.
  The first smoke reported 22/22 while Reflexion was echoing — it only checked that *something*
  came back. A smoke test needs to assert what the answer is, not that one exists.
- [x] **Paywall verified in production**: an unentitled caller gets 14 of 63 lines, no
  `build_graph`, and the preview is real readable code.
- [ ] **Promote the founder's workspace to `plus`** — the paywall applies to you too: your
  workspace is `free`, so your own Code tab is a preview. Needs `CALYPR_ADMIN_TOKEN` on Railway,
  then `POST /admin/workspaces/<id>/plan {"plan":"plus"}`.
- [ ] **`PRICING-SPEC.md` reconciliation before Week 9**: no credit rate exists for the Image or
  TTS nodes; the launch matrix predates BYO frontier models. Migration renumbered to **`0010`**
  (`0009_assistant_model` is taken); `provider_key`/`workspace.plan` already shipped in 0007/0008.
- [ ] **`e2e/tests/phase-assistant-model.spec.ts:166` is environment-sensitive** — passes in CI
  and on a machine with no `.env`, fails identically on unmodified `main` when real provider keys
  are present (it asserts `.last()`, which becomes a real model answer). Pre-existing, not a
  regression; needs a stable assertion on the notice itself.

Outstanding work, roughly in priority order. Shipped phases are summarised at the bottom for
context. The visual canvas → LangGraph compile → ownable-Python round-trip is built through
Phase 5 (control flow, tools, Reflexion, RAG); what remains is mostly **getting the backend to
production** and the **RAG ingestion** next pass.

## 🟢 Tavily live + multi-Tool-node dispatch — DONE (2026-07-22), merged to main (PR #41, `4a7ae75`)

Surfaced by the user wiring Notion (MCP) + Tavily to one agent and getting "I can't access the
web/Notion" from a model that had (unknowingly) been given zero tools. Four bugs, all found while
chasing that one report; each is independently gated by a test that fails when its fix is
reverted. **User-confirmed working end-to-end in production** (Tavily + Notion together, one
agent) — the strongest kind of proof this file has for a Tools-node change.

- [x] **Tavily now executes on the canvas** (`packages/nodes/src/calypr_nodes/tools_catalog.py`)
  — was `runtime=None` (codegen-only); every call came back as a canned "codegen-only" message
  regardless of a saved key, which the model then relayed as if the integration were broken. Now
  a real `httpx.post` against Tavily's REST API, same never-raise/never-inline-a-key contract as
  the Unsplash/generic-HTTP providers. Keyless deliberately does **not** serve stub results the
  way Unsplash does — placeholder search results would be facts the agent relays as real, so it
  says plainly that search is unavailable instead. Codegen unchanged (still emits
  `TavilySearch(...)`), so the round-trip parser's recognizer needed no changes.
- [x] **An agent wired to >1 Tool node could only reach one of them** (`agent.py`, `tool.py`,
  `compile.py`) — binding already unioned across every wired Tool node (the model could always
  *choose* between Notion and Tavily); dispatch couldn't keep up, because every ReAct edge shares
  the `tools` condition, so the branch map collapsed to whichever node was declared last. A call
  routed to the wrong node came back `"web_search is not a valid tool, try one of
  [search_images]"`. Fixed with `ctx.tool_owners` (call name → owning node id) on the router, plus
  fan-out + own-calls-only scoping on the Tool node so two nodes called in one turn don't
  double-answer the same `tool_call_id`. Single-Tool-node graphs are untouched. **Known gap,
  tracked separately:** generated Python still has this collapse — needs the round-trip parser
  updated in step (it discriminates Router vs. ReAct by the routing function's name).
- [x] **A Tool node wired from a Router bound nothing** (`validate.py`) — only
  Agent/Responder/Revisor consume bound tool schemas; a Tool node hanging off a Router (which is
  what the AI assistant had generated for "read my Notion workspace") handed its schemas to a
  node that discards them, so the agent silently got zero tools. `validate_graph` now rejects an
  unbound Tool node (`tool_node_unbound`) — the assistant repairs against this same validator, so
  it self-corrects rather than shipping the broken shape.
- [x] **The assistant had never seen a Tool node wired correctly** (`services/assistant/.../
  prompt.py`) — not one of its six few-shots contained a Tool node, so on "read my Notion
  workspace" it reached for the one control-flow shape it *had* seen (a Router branch) and
  produced exactly the broken topology above. Added `notion_assistant()` as a worked ReAct
  few-shot, plus a hard rule for the multi-tool case (one Tool node per provider, each wired
  straight to the agent, no router needed to choose between them).
- [x] **LLM Router leaked its branch decision into the transcript** (`router.py`) — found while
  testing the above, unrelated to tools. `collect_text`'s streaming defaulted on, so the
  classifier's reply (a branch name like `"respond"`) streamed to the playground and landed glued
  to the end of the actual answer (`"...ask!respond"`). `stream=False` on that one call; reverting
  it reproduces as a doubled/glued reply in the test.

## 🟢 MCP tool node + credential vault + connectors + BYO keys — DONE (2026-07-20), merged to main (PR #27, `8a79e0e`)

Universal MCP support for the Tools node, plus the credential-vault subsystem it needed
(connectors, Notion Tier A, BYO provider keys). CI (`build-test`) green at merge; Vercel Preview
still fails independently (pre-existing infra issue above, not code).

- [x] **MCP provider on the Tools node** (`packages/nodes/src/calypr_nodes/tools_catalog.py`,
  `tool.py`) — reuses the existing `type="tool"` node (no new node type); `provider="mcp"` drives
  a real HTTP MCP server via `langchain-mcp-adapters` (`streamable_http`/`sse`). Async tool
  discovery runs on a dedicated thread (compile is sync but called inside a live event loop);
  results cached per URL. `discover=False` keeps codegen offline (never hits the server at
  generate time). Bearer token is runtime-only — generated code reads `os.environ`, never a
  literal. `mcp_react()` framework + `tpl_notion_assistant()` template in the gallery.
- [x] **Credential vault** (`apps/api/src/calypr_api/vault.py`) — Fernet envelope encryption,
  master secret from `CALYPR_VAULT_KEY` (any string). Insecure dev fallback key in local/CI;
  **fail-closed** in production or whenever `CALYPR_INTERNAL_KEY` is set (closes a
  misconfiguration footgun where secrets would silently encrypt under the public dev key).
- [x] **Connectors** (`connector_credential` table + RLS, migration `0006`; `/connectors` CRUD +
  `/test` live-ListTools probe) — Tier B (paste any HTTPS MCP URL + optional bearer, encrypted)
  ships now. Canvas Tool node gets a **Connector** dropdown resolving to url+headers server-side
  at run time (`resolve_graph`, injected just before compile) — the DSL only ever carries a
  `mcp_connector_ref` handle, never a secret. SSRF guard added post-review: Tier B URLs resolving
  to loopback/private/link-local/metadata addresses are rejected on real deployments (save + use
  time), off in local dev/CI.
- [x] **BYO provider API keys** (`provider_key` table + RLS, migration `0007`; `/provider-keys`
  GET/PUT/DELETE) — Settings → API Keys: pick OpenAI/Anthropic/Tavily from a dropdown, paste a
  key, it's encrypted and shown masked (••••) once saved. `model_for`/`image_model_for`/
  `tts_model_for` gained an optional `keys` map — a workspace key overrides the server env for
  that provider, else falls back to env (every param optional, fully backward-compatible; 356+
  tests unaffected).
- [x] **Settings → Connectors panel** (`apps/web/src/components/canvas/SettingsPanel.tsx`) —
  sidebar tab renamed Settings→**Connectors** with a Cable icon; section titles in Geist Mono to
  match the Blocks tab; Connected Accounts / MCP Servers / API Keys sections.
- [x] **Notion Tier A verified working end-to-end in dev** — classic public-integration OAuth →
  encrypted bot token → self-hosted `@notionhq/notion-mcp-server --enable-token-passthrough`
  (Docker, `infra/docker/compose.yaml`, port 3333). Live-tested: `/connectors/{id}/test` returns
  all 24 Notion tools through vault → decrypt → `Notion-Token` header → MCP server → Notion.
- [x] **Notion Tier A — LIVE in production** (2026-07-22). No longer deferred:
  - [x] **`notion-mcp` hosted as its own Railway service** — packaged in `infra/notion-mcp/`
    (PRs #39/#40). Bearer auth via `AUTH_TOKEN`; the "internal port == published port" rule
    turned out to be local-only (with bearer auth the server skips `Host` validation).
  - [x] **OAuth `state` parameter** shipped (PR #38) — `connect` mints a signed, workspace-bound,
    10-minute state (`calypr_api/oauth_state.py`); `callback` refuses anything else *before* the
    code is exchanged. Closes the CSRF gap from the security review.
  - [x] `CALYPR_NOTION_*` set in prod; redirect URI registered.
  - [x] **User-verified in production**: Notion + Tavily wired to one agent, working end to end.
  - See `infra/CONNECTORS.md` (setup) and `infra/PRODUCTION.md` (runbook + security posture).
- [x] **Tavily wired to the vault key** — DONE (2026-07-22, see below): `resolve_tool_keys` now
  injects a workspace's saved Tavily key into `ToolConfig.api_key` the same way it already did
  for Unsplash.
- [ ] **Fast-follows, not started:** stdio transport for MCP (codegen-only, local dev escape
  hatch); egress allowlist toggle per workspace (the SSRF guard is a blanket private-range block,
  not configurable); token refresh/reconnect job for Notion (OAuth refresh tokens expire — no
  "Reconnect" badge yet); `FORCE ROW LEVEL SECURITY` on `connector_credential`/`provider_key` if
  the prod DB role turns out to be the table owner (app-level `workspace_id` filters already
  cover this, so it's belt-and-suspenders, not urgent).

## 🟢 Image + Voice (TTS) + Upload blocks — DONE (2026-07-18), merged + confirmed live in prod

Three new media/vision node types shipped in one day, each via its own PR, each auto-deployed by
Vercel + Railway on merge. **User-confirmed working in production**, not just automated checks:
Image + Voice tested live on the playground; Upload/vision tested live end-to-end (attach → real
gpt-4o-mini review) after the blob-token incident below was fixed.

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
- [x] **"Translate & speak (EN → 中文)" template** (2026-07-18, `tpl-translate-speak`): pure
  composition, no new node types — Input → Agent (output-only Simplified-Chinese translator,
  gpt-4o-mini) → Voice (gpt-4o-mini-tts, Mandarin-pronunciation `instructions`) → Output. One run
  yields two outputs: the streamed 中文 transcript and the spoken translation's player below it.
- [x] **Upload block + vision loopback** (2026-07-18, PR #20) — users attach an image (≤5MB,
  playground + share page) and a vision Agent reviews it. `Msg.images` + OpenAI-adapter
  multimodal content (Anthropic drops images — v1 limitation), `upload` node (state.images →
  image_url HumanMessage), `POST /uploads` + `/share/{token}/uploads` (5MB cap, type allowlist,
  magic-byte sniff; blob `uploads/` prefix), attach UI (paperclip + thumbnail chip) in both
  chats, `RunRequest.images` (≤4, blob/data-URI-only — anti-SSRF). Templates: `tpl-label-reader`
  + `tpl-alt-text` (Input → Upload → Agent → Output; the Agent prompt is the specialization).
  **Confirmed working in production** by the user after the blob-token fix below.
- [ ] **Vision/upload follow-ups**: Anthropic image blocks; per-token rate limiting on share
  uploads (abuse guard — currently only token-gated + 5MB); blob GC now also covers `uploads/`;
  non-image files (PDF receipts); multi-image attach UX.
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
- [x] **Provision `BLOB_READ_WRITE_TOKEN`** (2026-07-18) — Vercel Blob store (public,
  Portland/PDX1, base URL `https://pr7homsjyvqypjew.public.blob.vercel-storage.com`); token set
  in Railway `calypr-api`. **Incident (fixed same day):** the token was pasted with its
  `.env`-style double quotes, so Vercel 403'd every upload and media silently fell back to
  `data:` URIs — the earlier "blob URLs verified" claim was wrong. Fixed the Railway value and
  hardened `put_blob` to strip stray quotes/whitespace (regression test added). Verified for
  real: prod `POST /uploads` returns a public blob URL that serves 200.
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
- [x] **Vercel PREVIEW builds fail** — DONE (2026-07-22). Root cause found: Neon (the Postgres
  Marketplace integration) provisions one database branch per preview deployment and never
  deletes it when the PR closes; the workspace's plan branch limit was hit around 2026-07-12
  (first broken preview was PR #10 — a Python-only change, confirming it was never the code).
  Every failing deployment showed `Builds ╶ . [0ms]` with the real error one layer down, under
  "Provisioning Integrations": `Branch limit reached. Upgrade your plan or delete unused
  branches.` Fixed by deleting old preview branches in the Neon console; confirmed with a clean
  preview deploy (draft PR #42, closed after). **Not yet fixed**: nothing auto-deletes a preview's
  Neon branch when its PR closes, so the count will climb back up over the next few weeks unless
  Neon's Vercel integration has an auto-cleanup setting — worth checking before this recurs.
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
- [x] **Week 6** — per-node config `parse()` recognizers (see the Week-6 section below). Done.

## 🟢 Beta access — entitlement primitive + round-trip to a cohort — DONE (2026-07-21)

PR #32 (`feat/beta-access-entitlements`, open). Gates the round-trip on a **workspace tier**
instead of a dev flag, so it can run as a closed beta **in production**.

**Why not leave it dark:** `ROADMAP-6M.md` §Month-2 — *"at the wall, do they drop into code and
continue, or churn? This ratio is the whole thesis."* That ratio is unmeasurable while the feature
is off (`parse_applied`/`parse_degraded` never fire), so the Month-2 gate can never close and we'd
reach Month 3 (Stripe) having never validated the thesis we're charging for.

> **REVERSED 2026-07-22 — closed-product pivot.** The paragraph below decided *beta ≠ paywall*:
> the round-trip would stay free core because it was the "no ceiling" promise and Week 11 would
> OSS the parser. Both halves are now off. The product is **closed** (no OSS launch), and **code
> export is the paid feature** — `has_roundtrip` never graduates to `return True`, and
> `deps.require_code_export` enforces it on `POST /parse` rather than leaving the paywall to the
> UI. The Month-2 ceiling-resolution gate above is also retired: it measured the *open* product's
> thesis. Kept verbatim because it's the reasoning a future reader will want when asking why the
> plan column exists at all. See `PRICING-SPEC.md` §1.

**Decided: beta ≠ paywall.** `beta` gates on our confidence, `plus` on value capture. The
round-trip stays **free core** — it *is* the "no ceiling" promise, and Week 11 OSSes the same
parser on PyPI. Paid differentiation stays on capacity (projects/credits/platform models) per
`PRICING-SPEC.md` §1, which is already fully decided — no pricing redesign needed.

- [x] **Migration `0008`** — `workspace.plan` (`free|beta|plus`) + `waitlist` table. Documents why
  `waitlist` is the one table with no `workspace_id`/RLS policy (pre-signup writers): write-only
  publicly, readable only via the admin token.
- [x] **`entitlements.py`** — `has_roundtrip()`; one line changes when the feature graduates.
- [x] **`/workspaces/current` returns `plan`**; canvas gates `CodeView` on it. Build-env +
  `localStorage` remain **dev** overrides — required, because the gate turns the Code tab into a
  `<textarea>` and 5 other specs assert `toContainText` on `code-output`.
- [x] **Waitlist actually stores** — it was silently discarding every signup behind a TODO.
  `POST /waitlist` normalizes, is idempotent, returns 204 and never rows (non-enumerable).
- [x] **Operator promote route**, `CALYPR_ADMIN_TOKEN`-guarded, **fails closed** (404 when unset
  or wrong). No admin UI — a curl suits ~10–25 partners.
- Verified: **853 pytest** (12 new), **39 e2e** (+2 — a `beta` workspace sees Apply with no local
  opt-in, a clean A/B vs the `free` case; and the waitlist persisting), ruff/tsc/eslint/prod build
  green, migration reversible.
- [ ] **To run the beta:** set `CALYPR_ADMIN_TOKEN`, then
  `curl -X POST $API/admin/workspaces/<id>/plan -H "x-admin-token: $TOKEN"
  -d '{"plan":"beta","email":"partner@example.com"}'`. Manual SQL fallback:
  `UPDATE workspace SET plan='beta' WHERE id='<uuid>';`
- [ ] **Then:** watch `parse_applied` / `parse_degraded` in PostHog against the Month-2 gate.

## 🟢 Apply to canvas — the loop closes (MVP Week 8 — reverse round-trip) — DONE (2026-07-21)

MERGED to main (PR #31, squash `c47f6ff`). Plan: `MVP-EXECUTION-PLAN.md` Week 8. The reverse
round-trip finally reaches the user: edit the generated Python, press **Apply to canvas**, get
nodes back. **Ships gated OFF** — deliberately not live in production yet.

- [x] **`POST /parse`** beside `/codegen` (`routers/agents.py`) — pure + unauthenticated, returns
  `{graph, warnings, degraded_nodes}`, **never 500s** (unrecognised functions degrade to Code
  nodes and are reported). `calypr-roundtrip` added to `apps/api` deps; `graph_parse_requested`
  → PostHog. Tests: round-trip, hand-edited prompt recovered, garbage input, degradation.
- [x] **Web** — `/api/parse` proxy + `parseCode()`; `CodeView` editable mode + **Apply to canvas**
  with inline warnings and an honest "N steps kept as custom code" notice. Reuses the canvas's
  existing apply path (`applyAssistantGraph` → `applyGraphToCanvas`, now shared with the AI
  assistant), so **an apply is undoable** like any other graph change.
- [x] **Ceiling-resolution events** — `code_edited`, `parse_applied`, `parse_failed`,
  `parse_degraded`. These are the Month-2 metrics (did the user who hit the ceiling come back?).
- [x] **Gate** (`lib/flags.ts`): off unless `NEXT_PUBLIC_ROUNDTRIP_ENABLED=1` at build time **or**
  `localStorage["calypr:roundtrip"]="1"` per browser; read via `useSyncExternalStore` (no
  hydration mismatch). The per-browser route exists because the gate turns the Code tab into a
  `<textarea>` (text in `.value`, not `textContent`) — **5 existing specs assert
  `toContainText` on `code-output`**, so a global build flag would have broken them. It also lets
  us dogfood a deployed build without shipping to users.
- [x] **`e2e/tests/phase8-roundtrip.spec.ts`** — edit prompt → apply → canvas + config panel
  reflect it; edited agent still streams; unparseable code reported with the canvas untouched;
  hand-written step degrades to a custom-code node; **UI absent without the opt-in** (production
  behaviour asserted, not assumed).
- Verified: **840 pytest, 38 e2e (whole suite — no regression), ruff + tsc + eslint clean, prod
  build green with the flag unset.**
- [ ] **To go live:** set `NEXT_PUBLIC_ROUNDTRIP_ENABLED=1` on the deployment (rebuild required).
  Holding per the decision to keep Weeks 6–8 out of production for now.
- [ ] **Next: Month-2 gate review** — read `parse_applied` / `parse_degraded` in PostHog once
  enabled, against the ≥50%-of-code-droppers-stay-14-days and ≥40%-30-day-retention bars. Then
  Month 3 (Week 9 = Stripe billing core).

## 🟢 Edit-survival mutation suite (MVP Week 7 — reverse round-trip) — DONE (2026-07-21)

MERGED to main (PR #30, squash `69efa73`). Plan: `MVP-EXECUTION-PLAN.md` Week 7. Week 6 proved the
round-trip on *pristine* generated code; Week 7 measures what survives when a **human edits the
code first** — the entire point of the round-trip. Survival is now a number, not a hope.

- [x] **Mutation operators** (`services/roundtrip/tests/mutations.py`) — 11 realistic hand-edits
  (prompt, temperature, channel rename, inline comment, trailer deletion, formatting reflow, edge
  add/remove, node-id rename, docstring rewrite, hand-written node), each paired with the
  expectation its parse must satisfy. Node-targeted edits expand over **every** node so each
  recognizer is actually stressed, not just the first node's.
- [x] **Two-tier gate** (`tests/test_mutations.py`) over **378 (graph, edit) pairs**:
  - **Robustness — asserted 100%:** never raises; topology (ids/edges/entry) + state channels come
    back exactly as the edit implies; **never misclassifies** (a node is its true type or a
    degraded `code` node, never some *other* type). A bad edit can cost one node's structure — it
    can never silently corrupt the graph.
  - **Clean absorption — measured, gated ≥95%:** in-idiom edits recover with no degradation and
    the change reflected in config; out-of-idiom edits degrade *exactly* the touched node.
- [x] **Measured: robustness 100% / clean absorption 100%** (307 in-idiom pairs). Table printed by
  `pytest -k survival_rates -s`; documented in `services/roundtrip/README.md` (OSS content).
- [x] **Gate verified to bite** — reintroducing the Week-6 retriever over-match turns 36 robustness
  assertions red. That bug class is **invisible** to the Week-6 fixed-point test (pristine code
  keeps the docstring intact), which is exactly the value Week 7 adds.
- [x] **Recognizer hardening (plan's conditional Deliverable 4):** `input`/`output` gained
  structural fallbacks, so rewriting their docstring no longer costs them their type (their config
  is fully recoverable from structure — nothing is guessed). Agent-family nodes still degrade on a
  docstring rewrite **by design**: the docstring is the only record of *which* agent variant it is,
  so guessing would silently change behaviour while degrading preserves the code verbatim.
- Still **dormant** — pure test + docs, no user-facing surface. 836 passed, ruff clean.
- [ ] **Next: Week 8** — ship the loop: `POST /parse` in `routers/roundtrip.py`, editable
  `CodeView.tsx` + **"Apply to canvas"**, ceiling-resolution events (`code_edited`,
  `parse_applied`, `parse_failed`, `parse_degraded`), Playwright `phase8-roundtrip.spec.ts`.
  This is the week the round-trip becomes user-visible.

## 🟢 Node-config recognizers (MVP Week 6 — reverse round-trip) — DONE (2026-07-20)

MERGED to main (PR #29, squash `71ceb71`). Plan: `MVP-EXECUTION-PLAN.md` Week 6. The
reverse parser now recovers each node's **type + config**, not just topology — before this every
node degraded to a Custom Code block. Makes `canvas → code → edit → canvas` reconstruct the real
graph.

- [x] **Infra** — `NodeParseContext` + `BaseNode.parse()` hook in `registry.py` (inverse of
  `codegen()`); shared AST helpers in new `packages/nodes/_parse.py`; dispatcher in
  `services/roundtrip/parse.py` tries recognizers in priority order and **degrades to a `code`
  node on no match (never misclassifies)**.
- [x] **13 recognizers**, each `parse()` beside its `codegen()` so forward/inverse can't drift:
  `input`, `output`, `agent` (all 6 types, scaffold-stripped prompts), `router` (rules + llm),
  `tool` (demo/tavily/mcp), `retriever` (demo/pgvector), `responder`, `revisor`, `evaluator`,
  `memory` (buffer/summary), plus post-plan `image`, `tts`, `upload`.
- [x] **Registry-wide property test** — codegen fixed point
  `generate(parse(generate(spec))) == generate(spec)`, byte-identical over golden + all 14
  STARTERS (**22/22, zero degraded, zero misclassification**). Equivalence relation documented in
  new `services/roundtrip/README.md` (seeds the Week-11 OSS launch). Full pytest + ruff green.
  - Config the code doesn't express (`max_tokens`, runtime `api_key`, cosmetic `label`) reverts
    to defaults — lossless for the round-trip since it doesn't change the generated code.
  - Recognizers key on the generated docstring + structure. Hardening against rewritten
    docstrings / heavy reformatting is **Week 7** (mutation / edit-survival suite, ≥95% target).
- Pre-existing unrelated failure noted: `apps/api/tests/test_uploads.py::
  test_share_upload_unknown_token_404s` (503 vs 404, needs a live DB) — fails identically without
  this change.

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
