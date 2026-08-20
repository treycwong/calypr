# Calypr — TODO

> **Everything currently open, in priority order.** Sections below this one are the historical
> record — what shipped and why. Updated 2026-08-20.

## ⏭️ NEXT — what's actually blocking

**The live payment loop is now proven end-to-end (2026-08-02):** a real `free → plus` through the
Upgrade button on the live endpoint — `checkout.session.completed` mapped the customer and
`invoice.paid` granted 2,000 credits, both delivered **200** — so **the live webhook signing
secret is verified** (the long-standing §1 worry). Credits then debited on real AI usage.
**Two gaps remain before this is fully closed** (see §1): the **cancellation path is still
unproven live** (`customer.subscription.deleted` — do a real cancel → refund), and the prod logs
show interleaved `POST /billing/webhook 400`s, likely a **duplicate/test webhook endpoint aimed
at the prod URL** with a mismatched secret — audit Stripe → Developers → Webhooks (there should be
exactly one live endpoint).

**Multiple workspaces shipped 2026-08-02** (PR #59, live and verified): Free 1 workspace /
3 projects / 500 MB, Plus 3 / 20 / 5 GB, all pooled per account. It also closed two bugs that
predate it — conversation threads were not bound to a tenant, and a new user's first runs streamed
unmetered. Storage is displayed rather than enforced, on purpose. See the section below.

**Account deletion and the downgrade path shipped 2026-08-04** (PRs #60–#63, #65, #66 — all live): a real
Delete Account, and a lapsed Plus subscription that no longer destroys run state or claws back
credits, with over-cap workspaces/projects locked read-only rather than deleted. See the section
below. **Four things it left open**, none blocking: a real Stripe cancellation and a real blob
delete are still unverified by hand (`ACCOUNT-DELETION-RUNBOOK.md`); ~~image-node~~ and share-page
uploads write no row so those blobs survive deletion (**image/TTS output fixed 2026-08-06 by
`0019`'s `asset` table**; share-page uploads still unattributable); the Usage tab renders `3 of 1`
as an ordinary meter when over-limit; and **Vercel preview deployments have been failing all day
while production is fine** — proven environmental with a control branch, still true on 2026-08-06
(#73 and #74 both showed a red Vercel check and merged and deployed cleanly), but worth a look at
the dashboard.

**Playground history + media shipped 2026-08-06** (PRs #73, #74 — both live and verified in
production): Playground conversations are now durable and per-project, generated images and audio
are recorded in an `asset` table and browsable from a Media rail panel, and Stop actually stops a
run mid-answer. See the section below. It **closes half of §3's blob-GC item** — generated media
is now recorded, deletable and collected on account deletion — and leaves the orphan sweep for
pre-0019 objects open. Two bugs fixed in passing: a stopped run lost its answer entirely
(`GeneratorExit` is not an `Exception`), and `gc_checkpoints` collected actively-used threads on
the strength of their oldest run.

**Study mode, the Workflows library and the project-cap upsell shipped 2026-08-20** (PRs #84,
#85 — both merged and live): projects can now be drills that keep score, the dashboard's Templates
stub is a real workflow gallery, and a free account out of project slots is offered Plus instead of
`save failed (402)`. Three bugs surfaced on the way, each fixed with a test that bites — the
Evaluator was streaming its private "SCORE: 5" onto the end of the user's answer, Share minted
links for a graph the canvas had already moved past, and the card specimen taught its own subject
so a German deck came back in Chinese. See the section below.

**The canvas toolbar shipped 2026-08-13** (on branch, not yet merged): React Flow's stock
`<Controls />` and `<MiniMap />` are replaced by one weavy-style bar centred on the canvas —
arrow/hand tools, undo/redo, and a live zoom readout — with V/H/⌘Z/⌘⇧Z/+/− shortcuts and
Figma-style scrolling. See the section below; note that `.react-flow__controls` was the e2e
readiness sentinel and is now `canvas-toolbar`.

§2 is closed: billing is enforced end-to-end and live. §3 is the money-safety work that should
land before real charges, none of it blocking.

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
- [x] **Cancellation PROVEN in production (2026-07-24)** — `plus → free` observed end-to-end on
      the deployed endpoint for the first time: `customer.subscription.deleted`
      (`evt_1TwcdaQ4CLwWKY6VUnNcwRPa`) delivered **200** at 06:49:14, recorded in `stripe_event`,
      and workspace `914f15cf-9cde-430c-bb1a-186b9d88fa47` flipped `plus` → `free`.
      **It failed the first time, and the failure is the lesson.** The first cancel was delivered
      twice and rejected **400 "bad signature"** both times — Railway held the *live* webhook
      secret (`whsec_FE…`) while the subscription being cancelled was *test* mode
      (`whsec_PX…`). Signature verification runs before anything else, so nothing was recorded
      and the plan silently stayed `plus`: **a real customer cancelling would have kept full Plus
      access indefinitely, with no error surfaced anywhere.** Test and live have separate
      endpoints and separate signing secrets — a mode mismatch is invisible until you look at the
      HTTP status. Proven by switching Railway to the test key set and hitting *Resend* on the
      already-failed event (no re-subscribe needed).
      Observe any of this with `apps/api/scripts/observe_billing.py` (read-only):
      `railway run --service calypr-api -- uv run python scripts/observe_billing.py --customer cus_…`
- [x] **`free → plus` PROVEN through the real button (2026-07-24)** — paid in test mode from a
      genuinely `free` workspace: `free` → **`plus`**, balance `0` → **2,000.000 credits**,
      `grant_cycle_anchor` `2026-07-24`, ledger row `grant 2,000 source=stripe
      ref=in_1Twd5XQ4CLwWKY6V5670cQJg`. **The whole loop is now observed end-to-end on the
      deployed endpoint: `free → plus → free → plus`.**
      One thing this run confirmed by accident: `invoice.paid` landed at 07:00:11, a second
      *before* `checkout.session.completed` at 07:00:12. Stripe does not guarantee ordering, and
      the grant was issued by `invoice.paid` (ref is the `in_…` invoice id) with the checkout
      handler's grant correctly a no-op. Granting from **both** handlers, idempotent per cycle,
      is what stops a new subscriber landing on Plus with zero credits — don't "simplify" it to
      one.
- [x] **Railway restored to LIVE keys (2026-07-24)** — swapped to test to prove the loop, then
      restored and redeployed clean (`sk_live_…`, `whsec_FE…`, `price_1TwCr8Q4CLwWKY6VKVaMtiYY`;
      verified byte-length-identical to the pre-swap backup). The test subscription was cancelled
      **before** the restore, so the workspace is back to `free` honestly rather than by hand —
      once live keys are in, a test-mode event can never verify again, so the cleanup has to
      happen while the test keys are still loaded. Do it in that order if you ever swap again.
      Residue: the workspace keeps its 2,000 test-granted credits until the next cycle, when
      `grant_monthly` tops *down* to the Free grant (delta is negative by design — grants replace,
      never stack). Harmless, but it explains a Free workspace sitting above 100 credits.
- [x] **The LIVE webhook endpoint is verified (2026-08-02).** A real `free → plus` through the
      Upgrade button drove `checkout.session.completed` (→ plus, customer mapped) and `invoice.paid`
      (→ 2,000 credits) — **both delivered 200 on the live endpoint**, so the signing secret matches
      and the events are subscribed. Founder workspace `914f15cf` is now `plus` on live customer
      `cus_UzquujNm9DXuK2`.
- [ ] **Prove the cancel path live.** `customer.subscription.deleted` has still never been delivered
      live — the exact event a mismatch would silently swallow (a cancel that keeps Plus forever).
      Cancel the founder's live sub through the portal, confirm the row flips `plus → free`, then
      refund. Do this before onboarding a paying customer who might cancel.
- [ ] **Audit the live webhook endpoints — prod logs show interleaved `POST /billing/webhook 400`.**
      The 200s prove the live secret is right, so the 400s are deliveries whose signature doesn't
      verify — almost certainly a **second (test-mode) endpoint pointed at the prod URL** with the
      wrong secret. Stripe → Developers → Webhooks should list exactly one live endpoint at
      `…up.railway.app/billing/webhook`; delete any stray one.
- [x] **Two live-launch bugs found + fixed (2026-08-02).** (1) A **stale test-mode customer**
      (`cus_Uw5V71aLHnaox9`) stuck on the founder workspace 502'd live checkout/portal (`No such
      customer … exists in test mode`); cleared the field so checkout mints a fresh live customer.
      Hardening still open: catch Stripe `resource_missing` in `create_checkout`/`create_portal` and
      fall back to a fresh customer instead of 502. (2) `current_period_end` never populated —
      Stripe API `2026-06-24.dahlia` **moved it off the Subscription onto its items**; fixed in
      **PR #57** (`_period_end` reads item-level + closes an event-ordering race by mirroring the
      cycle at checkout time).
- [x] **LIVE (2026-07-23)** — live keys set on Railway and deployed; `/checkout` offers payment.
      Live webhook endpoint `we_1TwE88Q4CLwWKY6VoKTNJdc2` created (there was **none** — the
      `whsec_` originally supplied was orphaned, so a live payment would have charged the
      customer and never notified us). Live price is
      `price_1TwCr8Q4CLwWKY6VKVaMtiYY`) plus a **separate live webhook signing secret**. Keep
      live values on Railway only, never in `.env`.
- ⚠️ **`.env` had both TEST and LIVE blocks active**, and since later definitions win, the
      **live** keys were what actually loaded — it looked test-configured and wasn't. The live
      block is now commented out. Worth re-checking whenever those keys are touched.
- [ ] **Point the webhook** at `https://calypr-api-production.up.railway.app/billing/webhook`
      — Railway directly, *not* calypr.co: signature verification needs the exact raw bytes, and
      the signing secret belongs where the DB is. Events: `checkout.session.completed`,
      `customer.subscription.{created,updated,deleted}`, `invoice.paid`, `invoice.payment_failed`.
      **TEST endpoint: confirmed done (2026-07-24)** — it delivered to Railway and verified.
      **LIVE endpoint: confirmed (2026-08-02)** — a real payment delivered `checkout.session.completed`
      + `invoice.paid` 200 on the live endpoint. Remaining: prove the cancel path and audit for a
      stray second endpoint (both tracked above).
- [x] **Loop tested end-to-end through the actual button (2026-07-24)** — done on workspace
      `914f15cf…` ("Personal", `treycwong@gmail.com`) rather than `tracey@theflowops.com`, which
      satisfies the intent: a genuinely `free` workspace, paid via the real Upgrade button.
      Observed `free → plus → free`. (The warning still holds: a payment made *in the Stripe
      dashboard* carries no `client_reference_id`, so it correctly does nothing —
      `routers/billing.py:117-121` — which looks like a bug if you weren't expecting it.)
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

### 2. ✅ CLOSED (2026-07-25) — the credit grant: ledger + enforcement

**Done and live in production.** Both plans now spend a monthly grant on platform models and fall
back to BYO-key when it runs out; the ledger grants, debits and refuses; the balance is visible in
Settings and the canvas header.

Precisely what has been *observed*, as opposed to tested: **debiting**, on a real tenant-scoped
workspace in a browser — credits fall per run and the header tracks them. **Refusal at zero has
only been proven by the DB-backed tests**, never watched end-to-end. That is the same gap that
made the Stripe cancellation unprovable for a month, so it is written down rather than assumed:
set a workspace to `--credits 0.01` and run twice — the first completes, the second is refused.

The one item left below is a *question*, not a build task.

The section is kept for the record because two of the bugs it turned up were live and neither was
found by reading the billing code — both came from looking at production data:

- **BYO-key usage was charged twice.** Zero-rating keyed off a hardcoded frontier-model list
  rather than off whether the workspace had actually supplied a key.
- **Agent nodes metered at ~163× their true cost** (see §6) — over half of all recorded platform
  spend, and invisible until credits were enforced.

The original entry read: *"the biggest remaining gap, and it is a revenue leak — the grant
advertised on `/pricing` is not enforced anywhere."* It was right, and the leak is closed.

Build order (each step is useful on its own):

- [x] **`credit_ledger` table** (migration `0014`) — `workspace_id` + RLS, `delta_micro`,
      `kind` (`grant|debit|topup|adjust`), `source` (`run|assist`), `ref_id`, `model`. Balance is
      `SUM(delta_micro)`; cache it on `workspace.credit_balance_micro` in the same transaction.
      Store **micro-credits as integers** — `credits_for` returns a float on purpose (rounding
      per node would round many cheap nodes to zero), so round once, here.
- [x] **Grant 2,000 on `invoice.paid`** — the renewal hook already exists in
      `routers/billing.py::_apply`; it currently only re-asserts the plan. Free's 100/mo grant is
      lazy on first assist call in a new calendar month (no cron needed).
- [x] **Debit post-run** from the accumulated usage events — same hook that writes `run` /
      `run_usage` (`RunRecorder`), one ledger row per run/assist call. BYOK usage debits **0**:
      those tokens are billed to the user by their provider, never to us.
- [x] **Refuse the next run when spent** (SSE `code: "credits"`, not a 402 — `/runs` is a
      stream, so the error arrives in-band where the client already handles it) in `create_run` / `/assist` when the balance is spent. A run
      already in flight completes (bounded overshoot — `max_tokens` caps it); the *next* call
      402s. The web app already handles a 402 from `/parse`, so the shape is established.
- [x] **DECISION RESOLVED — option (a), 2026-07-24: credits first, BYO-key as the fallback.**
      **Both plans work identically**: spend the monthly grant on platform models (Free 100,
      Plus 2,000), and when it runs out either add your own key or wait for the reset. Grants
      replace per **calendar month** for both — `grant_monthly` compares `(year, month)`, so the
      old Plus copy promising a reset "on your next billing date" was wrong for a mid-month
      renewal and now says "next month".
      This reverses an option (b) that was built and then removed before it ever shipped: Free
      as BYO-key-only for canvas runs, per an older reading of `PRICING-SPEC` §1. It was correct
      to the spec and wrong for the product — a new Free user's very first Run became an error
      message telling them to go get an API key. `PRICING-SPEC` §1 and the `/pricing` copy have
      been updated to match what actually ships; **the spec is now the thing that was stale.**
      What survives from that work is the part that was right either way:
      `run_access.check_run_gates` skips the balance check entirely when every node runs on the
      workspace's own keys, and it resolves the **effective** model (node → workspace default →
      platform default) rather than reading `config["model"]` — an untouched canvas ships
      `model: ""` on every node, so a raw read would see nothing at all.
- [ ] **Is 100 credits the right Free grant now that it buys runs?** It was sized as an
      *assistant* budget. At `gpt-4o-mini` rates a small run costs ~0.006 credits, so 100 covers
      thousands of them and the ~$0.20/user/month costing in `PRICING-SPEC` §2 still holds — but
      that number was never chosen with runs in mind. Worth confirming against real usage rather
      than assuming it lands right by accident.
- [x] **Surface the balance SHIPPED** — Settings → Workspace already had the meter
      (`settings-view.tsx`, `data-testid="ws-credits"`); the canvas header now shows
      "N credits left" (`data-testid="nav-credits"`), linking to Settings and turning
      `text-destructive` at zero. It refreshes when a run settles (`Playground.onRunFinished`) —
      otherwise the number someone watches while deciding whether to run again is the one from
      before their last few runs.
- [x] **Assist gating SHIPPED — and the old entry here was wrong.** It claimed assist "is not yet
      metered against credits". It always was: `assist.py` has run `RunRecorder.start(...,
      source="assist")` since it shipped, and `metering._flush` debits from that. What was missing
      was the *refusal* — nothing called `check_can_run`, so an exhausted workspace kept drafting
      graphs and drove its balance further negative, bounded only by the in-memory daily call cap.
      `/assist` now returns `code: "credits"` when the balance is spent. The daily cap stays as a
      cheap abuse guard on top (still per-process — see §3).
- [x] **BYO-key usage was being charged twice — fixed (2026-07-24).** Not previously tracked here,
      and it was live: zero-rating keyed off `is_frontier(model_id)`, a hardcoded list of three
      models, rather than off whether the workspace had actually supplied a key. But
      `factory._key` prefers a stored key over the server env for *any* provider, so a Plus user
      with their own OpenAI key ran `gpt-4o-mini` on their own account **and** paid us credits for
      it — while `/pricing` promised "your own keys still run free, at zero credits".
      `model_access.runs_on_own_key` now answers the real question, and both `platform_cost_usd`
      and `platform_credits_for` take `own_key=`. The provider set is snapshotted at run start
      (`RunRecorder._byok`) so a key added or removed mid-run can't retroactively reprice it, and
      it reads provider *names* only — no vault round-trip, no secret material on the path that
      decides who pays.
- [x] **A run that costs us nothing is never refused (2026-07-24)** — the rule the two gates were
      missing, and the reason they're now one function. `check_can_run` looked only at the
      balance, so bringing your own key — the exact thing an exhausted user is told to do — left
      you blocked anyway: a Plus workspace at zero credits was refused a run billed entirely to
      its own provider account, and a Free workspace with keys for every node was refused for
      having spent an assistant budget that was never the constraint. Same bug on `/assist`, where
      it was a *regression*: adding the credit check there took away behaviour BYO-key users had
      the day before. `check_run_gates` now short-circuits before either refusal when
      `platform_key_models(...)` is empty, and `/assist` skips the check when
      `assist_on_own_key(...)`. Pinned by a test that asserts the bare `check_can_run` still
      refuses that same workspace, so it can't decay into testing a solvent one.
      **This is why a "use my own keys" toggle isn't needed**: storing a key already routes
      traffic to it (`factory._key`) and now already costs 0 credits, so the toggle would have
      been a switch for something that is simply true. The control that *is* missing is the
      inverse — "prefer platform credits even though I have a key stored", for someone whose own
      provider budget is tighter than the credits they've already paid for. Not built.

### 3. Before the first real charge (money safety)

- [ ] **UNEXPLAINED — a local database accumulated ~22,900 credits of cache/ledger drift.**
      `workspace.credit_balance_micro` had diverged from `SUM(credit_ledger.delta_micro)` on the
      shared dev workspace. **Production was checked and has none, on any workspace**, which is
      why this is not urgent — but the cause was never found, and "we don't know why the money
      column disagreed with its own audit trail" is not a state to have paying customers in.
      What was ruled out: `credits._write` is atomic (one transaction, SQL-expression update, no
      read-modify-write), and the one test that deliberately corrupts a cache
      (`test_the_ledger_wins_when_the_cache_drifts`) does so on a throwaway workspace.
      What *was* fixed is the diagnostic gap that hid it: `scripts/set_credits.py` sized its
      adjustment from the **cached** balance, so it preserved drift exactly and could never
      repair or report it. It now reads the ledger, prints any disagreement, and recomputes.
      A `recompute_balance` sweep with an alert on any non-zero difference would turn this from
      "nobody looked" into "we would know" — that is probably the right next step rather than
      hunting the original cause cold.
- [~] **Blob GC — half closed (2026-08-06, PR #73).** Every image/TTS generation used to write a
      permanent object under `runs/{png,mp3}/…` that nothing could ever delete, because nothing
      recorded it. `0019`'s `asset` table starts that record: media is now deletable from the
      Media panel (row + object together), cascades when its conversation is deleted, is counted
      in the storage figure, and is collected on account deletion. Failed object deletes park in
      `orphan_blob` and are retried by `POST /internal/gc/orphan-blobs` nightly.
      **What is still open:** an **orphan sweep for objects written before `0019`** — those have
      no row and are unattributable and unrecoverable, exactly like the pre-`0016` uploads. And
      media generated where `BLOB_READ_WRITE_TOKEN` is unset is deliberately not recorded (it is
      inlined as a `data:` URI instead), which is correct but means a deployment that later gains
      a token has a gap either side of that change.
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
- [ ] **Does storage ever become a hard cap?** It ships as a *displayed* figure (500 MB / 5 GB)
      bounded by run-state retention, not a 402 — see the workspaces section for why a byte cap
      isn't honestly enforceable yet. Two things would have to land first: per-project storage
      breakdown, and a **"clear run history"** action, because today a user at 100% has no lever
      (deleting a project doesn't free its runs' checkpoints). Live usage says there's no hurry —
      the one Plus account is at **3.0 MB of 5 GB**, 0.06%. Retention plus the project cap may
      simply be enough, and a byte cap on a $20 plan may be all support burden and no benefit.
- [ ] **Acquisition has no plan.** Cancelling the OSS launch removed the roadmap's only
      top-of-funnel (Show HN). The blog is shipped, indexed and has two posts — making it a
      deliberate channel is the cheap replacement, but somebody has to decide that.
- [ ] **Month-1 code-quality gate never ran** (≥70% would-merge, blind panel). Chosen
      substitute — the automated harness in `WEEK5-CODEGEN-EVAL-HARNESS-PLAN.md` Layers 1–2 —
      is also not built. It's a standing kill condition on everything downstream.

### 6. Known defects (not blocking, but real)

- [x] **FIXED (2026-07-25) — Agent nodes metered at ~163× their true cost.** `agent.py` resolved
      the model, used it to make the call, then reported `cfg.model` in the usage payload — which
      defaults to `""` (inherit). `pricing.price_for("")` falls back to the most-expensive known
      rate, deliberately, so metering never under-records. Two production runs with identical
      38-in/9-out counts recorded **$0.001815** and **$0.000011**; the second is correct.
      In production: 38 usage rows across 23 runs, **$0.349 of $0.659 total recorded platform
      spend**. Harm was confined to `run.cost_usd` — the figure the spend kill-switch sums, so the
      cap would have tripped early for everyone — because the ledger only began debiting
      afterwards. Image and TTS were never affected; their configs carry concrete model defaults,
      which is exactly why only agent nodes appear in the empty-model rows.
      **Found by reading production data, not the code.** Nothing in the billing tests would ever
      have caught it: they assert the arithmetic, and the arithmetic was right — it was being fed
      the wrong model id.
- [x] **FIXED (2026-07-25) — `simple_reflex` could never finish a tool loop.**
      `_latest_user_turn` truncated history to the bare user message, discarding the `tool_calls`
      the agent had just emitted and the result the Tool node had just written back. On re-entry
      it saw the original question again, asked for the same tool again, and ran to the recursion
      limit. **Every ReAct graph on `simple_reflex` failed** — structurally, not intermittently.
      Two lessons worth keeping. The error message asserted a cause it had not checked ("your
      graph has a cycle with no exit"), sending the user to delete a back-edge their correct
      topology needed; it now states only what is known. And this is a hole in the
      **accepted ⇒ runnable** guarantee of the node-wiring matrix: `Agent(simple_reflex) + Tool`
      is accepted by the validator and was not runnable. Worth asking what else the matrix accepts
      that only fails at runtime — the matrix checks wiring, not preset behaviour.
- [ ] **Generated Python collapses multi-Tool dispatch.** The runtime was fixed in PR #41
      (`ctx.tool_owners`); `services/codegen/generate.py:214` still emits one `tools_condition`
      branch, so an agent wired to two Tool nodes exports code that reaches only one of them.
      **Must be fixed before any Plus customer exports** — they'd get code that behaves
      differently from their canvas. Parser must change in step (it discriminates Router vs
      ReAct by the routing function's name).
- [ ] **Five config fields the engine never reads** (found by the 2c audit) — implement or
      delete: `agent.max_steps`, `agent.utility_criteria`, `input.mode`, `output.stream`,
      `tool.http_method`. The last is a real product gap: "call any JSON API" can't POST.
- [ ] **`e2e/tests/phase-assistant-model.spec.ts` is unreliable, in two separate ways.**
      (a) `:166` is environment-sensitive — passes in CI and on a machine with no `.env`, fails
      identically on unmodified `main` when real provider keys are present (it asserts `.last()`,
      which becomes a real model answer).
      (b) **The whole spec flakes about once per full serial run, with a *different* test failing
      each time** (`:38`, `:109`, `:121` all observed) and always passes in isolation. Confirmed
      pre-existing on 2026-08-02 by stashing an unrelated branch and reproducing on the baseline;
      CI's single retry usually masks it. Looks like a hydration race — the page is server-rendered
      and therefore clickable before React attaches, so an early click is swallowed. The fix that
      worked for the same problem in `phase13-workspaces.spec.ts` is to retry the click until it
      demonstrably had an effect (`expect(async () => {...}).toPass()`), rather than assume it did.
- [ ] **`calypr.co` (apex) does not resolve — only `www.calypr.co` works.** Found 2026-08-02.
      `dig`, `curl` and Python's resolver all fail to get an address for the bare domain while
      `example.com` resolves normally, so it is not a local/sandbox artifact. The domain sits on
      third-party nameservers (`dns1/dns2.registrar-servers.com`) with a **CNAME at the apex**,
      which is invalid per RFC and why resolvers reject it; `vercel domains inspect calypr.co`
      flags the nameservers ✘. Anyone typing the bare domain gets a DNS failure. Fix is an A
      record at the apex (Vercel's `76.76.21.21`) or moving the domain to Vercel nameservers.
      Unrelated to any deploy — DNS is not affected by a code merge.
- [x] **FIXED (2026-08-02) — the e2e suite ran differently on a developer machine than in CI.**
      `e2e/playwright.config.ts` pinned `STRIPE_*` and `CALYPR_ASSISTANT_MODEL` against a
      developer's repo-root `.env` but **not `CALYPR_INTERNAL_KEY`**, so a developer with a real
      key got tenant scoping and the billing gates switched on: 21 specs failed locally and passed
      in CI. Now pinned empty alongside the others. The general lesson is in that file's comment —
      anything the API reads from `.env` has to be pinned in the harness or the suite is not the
      same suite.
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

## 🟢 Study mode, Workflows library, project-cap upsell — DONE (2026-08-20), merged + live

Two PRs. **#84** added study cards and turned the dashboard's Templates placeholder into a real
Workflows gallery, carrying three fixes it surfaced. **#85** replaced the project cap's raw 402
with a pricing card. Both merged to `main`, deployed, and confirmed working in production.

### What shipped

- **Study cards.** An agent emits cards as ```` ```calypr-card ```` fences holding JSON; the chat
  renders them as interactive quiz and flashcard components and tallies a score. Four templates
  (Language flash cards, Quiz me on anything, Quiz me on my notes, Notion study quiz) and a
  study few-shot for the AI assistant.
- **The Workflows library** at `/dashboard/workflows` — all 18 use-case starters as a compact
  grid with real Unsplash covers; picking one creates the project and opens the canvas with its
  nodes wired. `/dashboard/templates` redirects.
- **The project-cap upsell** — a compact Free-vs-Plus card, reached from a Workflow card, the
  blank/template picker, and New Project.

### The decision that governs any future structured output

**The card protocol lives in the token stream, not on our wire.** An export is a single headless
`.py` that owns no Calypr dependency, so anything carried as a new SSE event is lost the moment
someone exports; a fence survives, and a buyer's own UI can parse it. The runtime, both SSE
routers, metering and `conversations.py` were untouched, and transcripts and history replay
carried cards for free. Put the next structured output in the text before considering a wire
change.

Study chrome is triggered by cards *arriving*, not by a field on the project — so it works
identically on the canvas, on a share link, and on a reloaded transcript, with nothing to
configure and no way for the setting and the behaviour to disagree. **No migration, no schema
change, no new node types.**

### Three bugs it surfaced, all worse than the feature

- **Internal nodes were talking to the user.** `collect_text` streamed `token` events, and all
  three of its callers are scaffolding — the Evaluator writes score/rationale, Memory a summary,
  the Router a branch. None writes to `messages`, yet the judge's `SCORE: 5 …` was appended to the
  end of the reply, same bubble, no separator. Now gated. **The gate is on the token emission
  alone, never on the writer:** silencing the writer would have taken `usage` with it and
  under-reported spend.
- **Share minted links for a graph you weren't looking at.** A link runs the *saved* graph and
  nothing tracked whether the canvas had diverged, so applying a template and hitting Share handed
  out a link to the previous version, silently — and applying a template keeps the project's own
  name, so nothing on screen contradicted you. It warns now, and deliberately does **not**
  auto-save: the canvas may be a template someone is trying on top of a project they want to keep.
- **The card specimen taught its own subject.** `_CARD_PROTOCOL` demonstrated the format with a
  real card (火 = fire); asked for a German deck, gpt-4o-mini copied the kanji along with the
  shape. Instructing it harder to "reproduce the block exactly" made it *worse* — that is an
  instruction to copy. The specimen now carries no subject at all (`THE QUESTION` / `RIGHT`).
  Applies to any exemplar-taught format.

### Never predict a plan cap in the browser

The upsell first decided "at cap" client-side from a row count against `PLAN_LIMITS`. Caps carry a
dev/CI carve-out (`enforce_project_cap` returns early with no internal key), so the browser
predicted a refusal the server would never make and **the dialog blocked the create flow for 17
e2e specs** that had already made three projects.

`can_create_project` now rides along with the workspace list the dashboard already fetches,
answered by `project_slots_left` — the same predicate `enforce_project_cap` calls.
`can_create` has worked this way for workspaces since it shipped and its docstring warns about
exactly this. The outage fallback is `true`, opposite to `can_create`: a missing menu item is a
quiet omission, but a `false` there tells a paying customer they are out of projects when the API
is merely down.

### Two smaller traps

- **`eslint-disable-next-line` followed by more comment lines does nothing** — "next line" points
  at the continuation comment. Put the rationale in a block comment *above* the directive.
- **`pytest` is not the gate.** PR #84 went red on `uvx ruff check .` (E501) after a green local
  pytest run. The full local sequence is `uvx ruff check .`, `pnpm --filter @calypr/dsl gen:check`,
  `pnpm -r --if-present typecheck`, `uv run pytest`, `pnpm --filter @calypr/e2e test`. `apps/web`'s
  eslint is **not** in CI, so a warning there blocks nothing — but ruff errors do.

### Verified

- 1696 Python tests, 161 e2e, ruff + typecheck clean. `build-test` green on both PRs.
- Against a live model: German → cards on the first turn, AWS exam → cards, plain support chatbot
  → no cards; a Japanese run still returns kanji, so the specimen fix removed the bleed rather than
  the characters. All 18 cover URLs return 200.
- Production deploys green on both Vercel (web) and Railway (`calypr-api`).

### Still open on this work

- **Cover photos are placeholders by decision** — to be replaced by hand later. They are committed
  static `images.unsplash.com` URLs in `apps/web/src/app/dashboard/workflows/photos.ts`, resolved
  once against the API so the app holds no key and makes no call. A template with no entry falls
  back to generative art.
- **e2e still writes fixtures to the local dev database.** Pointing it at a throwaway database was
  attempted and reverted: a migrations-only database is missing Better Auth's
  `user`/`session`/`account`/`verification` and LangGraph's `checkpoint_*` tables, which the dev
  database accumulated from other tooling, and 15 run/chat specs fail on it. Needs those seeded
  first — worth its own change.
- **A filter for the Workflows gallery** — by feature (Chat, Flash Card, Quiz, Media, RAG) rather
  than by the job-based categories that currently only order the grid. Derivable from node types
  and prompts rather than hand-tagged, so it need never drift.

---

## 🟢 Google sign-in, auth pages, provider disconnect — DONE (2026-08-20), merged + live

Three PRs in a day: Google as a second sign-in provider (#81), then disconnect/unlink plus an
auth-page pass (#82), then the icon-and-tooltip refinement (#83). All merged to `main`, deployed,
and confirmed working in production against a real GitHub + Google pair.

### What shipped

- **Google OAuth.** `socialProviders.google` beside `github` in `apps/web/src/lib/auth-server.ts`.
  That is the entire exchange-side change — Better Auth owns the OAuth flow inside Next, and the
  Python API only ever sees an opaque user id, so **the backend was untouched**.
- **`/sign-up` as its own route**, sharing one server-rendered `AuthPanel` with `/sign-in`.
  Mechanically identical (social sign-in creates the user on first use); separate so the heading,
  copy and URL can speak to someone who has never been here.
- **A WebGL backdrop** (`components/auth/AuthField.tsx`) on `@paper-design/shaders-react`, which
  was already a dependency and imported nowhere. Deliberately *not* the share page's `AsciiField`.
- **A real auth header** — wordmark left, the other auth page right. Not `SiteHeader`: its
  "Get Started" CTA points at `/sign-in`, which from `/sign-in` is a link to itself.
- **Disconnect per provider**, an icon + tooltip behind a confirm dialog, with the last provider
  dimmed and explained rather than removed.
- **`--color-brand`** promoted into `@theme inline`; cyan previously existed only as literals in
  the share route.

### The constraint that governs any future auth change

`billing_account.owner_user_id` **is** the Better Auth `user.id` (migration 0016 /
`resolve_account`). A duplicate user row means a duplicate billing account — a second plan, a
second credit balance, and the person's own agents invisible to them.

Better Auth's **defaults** already prevent that (`accountLinking.enabled`, implicit linking on,
`requireLocalEmailVerified` on), and both providers report verification honestly. So
`auth-server.ts` carries **no `accountLinking` block on purpose**, with a comment saying why.
**Never add `trustedProviders` to "fix" a refused link** — that reopens pre-registration takeover,
which given beta-invite matching on `x-calypr-user-email` hands out a paid feature.

Verified live: same-email GitHub → Google folded into one account, plan and workspaces intact.

### Two traps worth remembering

- **`session.freshAge: 0`** (set so GitHub users can complete account deletion) makes Better
  Auth's `freshSessionMiddleware` a **no-op on every endpoint relying on it**, including
  `/unlink-account`. Confirm dialogs are the only friction; middleware freshness buys nothing.
- **Per-frame shader props swallow clicks.** Driving the backdrop's `offsetX`/`offsetY` from React
  state re-renders the WebGL layer every frame and saturates the main thread hard enough that
  **links stop navigating with no error anywhere** — it took out 13 unrelated E2E specs that
  merely pass *through* `/sign-in`. Found only by running the suite on stashed `main` as a
  control. The parallax is now a `translate3d` mutated from the rAF loop; the shader's props never
  change.
- Related: **Tailwind v4 prunes a `@theme inline` entry pointing at a non-theme `var()`**, so the
  utility silently renders as `inherit`. Use literals. And the Next dev server serves stale CSS
  across branch switches — confirm against the production build before concluding anything.

### Still open on this work

- ~~`phase19-canvas-interaction.spec.ts:202` flakes ~1-in-6 **on `main`** (a 6px layout
  tolerance).~~ **Fixed 2026-08-20 (PR #84.)** It sampled the node mid-fit at `scale(2)`, so a 3px
  graph-space error read as 6px on screen; it now waits for React Flow's viewport transform to
  settle before measuring. Adding four templates was enough to shift the fetch timing and turn the
  flake into a hard failure.
- `/dashboard/settings` throws an unhandled `BetterAuthError: You are using the default secret` on
  the dev-auth path. Reproducible on untouched `main` via `phase-settings.spec.ts`. Pre-existing.
- The unlink round-trip has **no E2E coverage** and structurally cannot have any: the dev-auth
  session has no Better Auth `account` rows. Verified by hand in production instead.

---

## 🟢 Canvas & dashboard UI pass — DONE (2026-08-13), on branch

A day of design work bringing the canvas and dashboard toward the weavy.ai language. The toolbar
(section below) was the first piece; everything here rode after it, on the same branch.

### What changed

- **Sidebar is a tile system.** Blocks, Templates, Connectors and Models are all the same
  2-column grid of `TILE_CLASS` tiles — icon over label, monochrome, low-opacity white hover.
  Blocks gained icons (`components/canvas/node-style.ts`), which the canvas node cards read too,
  so a block looks the same in the sidebar and on the canvas. Rail widened to 52px, active tab
  ringed, AI icon is a robot, panel is 240px.
- **Blocks are dragged onto the canvas**, and **nothing auto-links any more** — see the trap
  below. Palette tiles carry a custom `application/calypr-block` MIME type so the canvas ignores
  dragged files and links.
- **Connectors**: account cards with a status dot and a 3-dot menu (Test / API key / Disconnect,
  with a confirm on disconnect). "API key" only appears on token apps; OAuth apps get
  "Reconnect", because there is no update endpoint and changing the credential means re-running
  the original handshake.
- **Models** (was "API keys"): a tile per provider. `0020` adds `provider_key.key_hint` — the
  key's last 4 characters, stored in the clear at write time so the UI can say *which* key is on
  file without the real one ever leaving the server. See that migration for why 4 is safe and why
  it can't be backfilled.
- **AI assistant** opens on an intro with four example prompts that send verbatim.
- **Media** tiles audio in the same grid as images.
- **Wires take the colour of the block they leave** (`NODE_STYLE.edge`), saturated `-500`s. Run
  state still wins, so the tint is *withheld* rather than overridden — an inline `stroke` would
  beat the CSS class and the cyan run glow would never show.
- **Dashboard**: full width, square cards carrying **deterministic generative art** seeded by the
  project id. A first pass drew each project's actual graph, backed by a new compact `preview`
  field on `AgentSummary`; both were removed. Drawing the graph was accurate and unhelpful — most
  graphs are a short line of dots, so every card looked the same, and finding a project at a
  glance is the one thing a dashboard has to do. The art carries no information, which is exactly
  what frees it to be distinctive. (`preview` came out of the API with it: an unread field on a
  list endpoint is just payload.) Cards are 16:10 and six-up at the widest breakpoint — square
  art at three-up made each one a poster. The composition is colour fields only; an earlier pass
  drew pale strokes over them, which at card size read as scratches on the glass.
- **Browser tab is named after the project**, and follows a rename as you type.
- Selected node is a solid grey card with a white-grey border (cyan means *running*), and the
  right panel now follows the selection.

### The traps, all of which cost real time

- **Removing auto-link broke eight suites at once.** Adding a block used to also wire it to the
  previously added one, and a third of the e2e suite quietly depended on that to produce a
  runnable graph. `helpers.ts` grew `connect()` / `buildChain()`, which drag handle-to-handle.
  Then `buildChain` itself was wrong: `fitView` on a canvas holding one node zooms to the 2×
  maximum, so by the third block the chain ran off-screen and its handles could not be clicked —
  it silently made 1 edge out of 2. It now zooms out and pans before wiring.
- **Next streams metadata**, so the route's `<title>` lands *after* hydration and overwrites
  anything a mount effect set. Rendering a `<title>` doesn't help either — React hoists it, but
  the browser reads the *first* title element and the streamed one is already there. The working
  answer is `document.title` plus a `MutationObserver` on `<head>` to re-assert it.
- **A hidden browser pane pauses `requestAnimationFrame`**, so anything animated is unobservable
  there: programmatic zoom looked completely dead, and a CSS transition made a selected node read
  as unselected. Both were fine under Playwright. Check the environment before rewriting working
  code.
- **Colours must be polled on the property that actually changes.** The node border is white in
  both states — only its alpha differs — so polling lightness passes instantly against an
  unselected node. Tailwind v4 also emits `oklab()` for `color-mix` and plain `lab()` for a
  literal palette colour, with different lightness ranges.
- **Two background utilities on one element** are resolved by Tailwind's output order, not the
  class attribute — so the selected wash has to replace `bg-card`, not sit alongside it.
- **The bare `transition` utility animates every animatable property over 150ms.** A node click
  landed its state change in ~45ms and then took another 150ms to *look* selected, which reads as
  lag. `transition-colors duration-75` fixed it.
- **Collapsing the left panel moved the canvas.** It is a flex child, so the container widens
  leftwards and every node slides 240px. The viewport is now compensated by exactly the panel
  width in a `useLayoutEffect`, so the graph stays where your eyes left it.

### Verified

`typecheck` + `lint` clean · **1557 python, 147 e2e**, zero failures. New specs: `phase16`
(toolbar), `phase17` (sidebar tiles), `phase18` (panel UI), `phase19` (canvas interaction), plus
`test_graph_preview.py`.

### Still open

- **The e2e suite shares the dev workspace with real projects.** Repeated full runs polluted it
  (waitlist rows, workspace caps) and produced a spread of failures that looked like regressions
  but reproduced on a clean tree. Point the suite at its own workspace before it touches
  something that matters.
- **Saved prompts is a tab with a "Coming soon" panel**, nothing behind it yet.
- **Multiple keys per provider with a primary per project** was scoped out: the table is one row
  per `(workspace, provider)`, so it needs a migration, CRUD endpoints, run-time resolution
  changes and a project→key link. Open question before starting: is the primary per project or
  per agent, given runs resolve keys per workspace today.
- **The favicon is cut from the vector mark** at 16–256px. A supplied 50px PNG was tried and
  reverted — it could only support 16/32/48 without upscaling.
- **The right panel's reopen control lives on the canvas edge**, not the header. It is the only
  route back to the Code tab with nothing selected, so it cannot be dropped without replacing it.
- **`TabsList` pins `h-8` through a `group-data-horizontal/tabs:` variant**, which out-specifies a
  plain height utility — so the Media/Playground tab strips need `h-12!` to breathe. Padding alone
  did the opposite of what it looked like it would: the strip stayed 32px and the labels squeezed.

---

## 🟢 Canvas toolbar — DONE (2026-08-13), on branch

React Flow's stock chrome is gone. `<Controls />` (the vertical zoom/fit strip, bottom-left) and
`<MiniMap />` (bottom-right) are replaced by one floating bar centred on the bottom edge of the
canvas, in the style of weavy.ai: **arrow · hand │ undo · redo │ `100% ⌄`**. New component
`components/canvas/CanvasToolbar.tsx`; wired into `app/canvas/page.tsx` through React Flow's
`<Panel position="bottom-center">`.

Shortcuts: **V** arrow, **H** hand, **⌘Z / ⌘⇧Z** undo/redo (unchanged), **+ / −** zoom. Scroll
moved to the Figma convention — the wheel pans, ⌘/ctrl+wheel and pinch zoom.

### The decisions worth remembering

- **Undo/redo moved out of the header rather than being duplicated.** They now sit next to the
  tool and zoom controls, within reach of the canvas being edited. The `data-testid`s came along
  unchanged, so `phase5`'s history test needed no edit at all.
- **Zoom is owned inside `CanvasToolbar`, not passed down.** `useViewport()` re-renders its caller
  on *every* viewport change; hoisting it into `CanvasInner` would have re-rendered the whole
  canvas shell on every pan. The dropdown carries only Zoom in / Zoom out — no fit, no 100% — by
  decision, which does mean **losing fit-view**; `fitView` on mount stays, so opening a saved
  agent still frames its graph.
- **One keydown listener for the whole canvas.** The V/H keys are bare letters, so they share the
  existing "ignore while typing" guard with undo/redo rather than adding a second listener with
  its own copy of the rule. That guard is now `isTypingTarget()` and covers `<select>` too —
  letters there jump to a matching option, and the config panel is full of them.
- **Arrow = marquee, hand = pan with nodes pinned.** Before this, left-drag always panned and
  marquee-selecting needed Shift. Holding **Space** still pans in either mode — that is React
  Flow's default `panActivationKeyCode`, free.

### The trap: `.react-flow__controls` was load-bearing in the e2e suite

It was the *canvas-is-ready* sentinel in `e2e/tests/helpers.ts` and inlined in ~12 specs. Deleting
`<Controls />` would have failed the entire canvas suite for a reason that looks nothing like the
change. All of them now wait on `getByTestId("canvas-toolbar")`. New spec:
`e2e/tests/phase16-canvas-toolbar.spec.ts` (5 cases — tool switching, the typing guard, the zoom
menu, the zoom keys, and that the stock widgets are actually gone).

### An environment trap that looks exactly like a bug

Driving the app through the in-app Browser pane, programmatic zoom appeared **completely dead** —
`zoomIn()` left the viewport at `scale(1)` from both the menu and the keyboard. Nothing was
wrong: a hidden browser pane pauses `requestAnimationFrame`, and React Flow's zoom runs through a
**d3 transition**, which never ticks. Anything animated is unobservable there. Playwright is the
real gate; it passed first try. Same class of thing as the Vercel-preview trap below — check the
environment before rewriting working code.

### Verified

`typecheck` + `lint` clean · **122 e2e passed**, zero failures.

---

## 🟢 Playground history + media — DONE (2026-08-06), merged to main

Two PRs, both live and verified in production: **#73** (`792af97`) durable history + media
library, migration `0019` · **#74** (`756307e`) Stop mid-run + audio descriptions.

A Playground transcript lived in React state and nothing else, so a reload lost it. Generated
media was worse: `store_asset` returned a blob URL that existed **only inside the message
markdown** — no row, so nothing could list it, search it, count its bytes, or reclaim it.
Inbound uploads have had an `upload` row since `0016`; the media we generate and bill for had
none.

**LangGraph checkpoints were never a substitute, and conflating the two is the trap.** They hold
the agent's *memory* of a conversation: TTL-collected per plan, no `workspace_id`, not
searchable. The transcript is now a separate durable thing the user owns. Consequence worth
internalising — a conversation can be fully readable while the agent remembers nothing of it, so
the History row badges "memory expired" rather than hiding.

`0019` adds `conversation`, `message`, `asset`, `orphan_blob`, each with the usual workspace RLS
policy.

### The three decisions that shaped it

- **`conversation.thread_suffix` stores the suffix, never the composed `ws:<id>:<suffix>`.**
  `threads.py` closed a cross-tenant hole by making the prefix always server-supplied; putting
  the composed id in a user-facing table read back out is how it drifts into being trusted input
  again.
- **Media is recorded via a new `asset` run event** (node → `run_stream` → `runs.py`), the same
  path `usage` already takes, so `packages/nodes` stays tenant-free — it gets code-generated into
  users' exported scripts. `store_asset` returns a `StoredAsset` and a row is written **only when
  `durable`**: a blob-less deployment still renders the file as a `data:` URI but records
  nothing, which keeps megabytes of base64 out of Postgres and guarantees `asset.blob_url` is
  always safe to hand to `delete_blob`.
- **`share.py` and `assist.py` record neither transcript nor media, on purpose.** Anonymous
  visitors have no identity to attribute to, so the only workspace available is the *owner's* —
  their Media panel filling with strangers' files is a privacy surprise, not a feature. Both
  refusals are commented at the call site; do not wire them up by symmetry.

`ConversationRecorder` mirrors `RunRecorder`'s contract exactly (own session, best-effort,
self-disabling, two round-trips, nothing per token) and is deliberately **not** folded into it:
that flush puts usage rows and the credit debit in one transaction, and a bad message payload
must never be able to roll back a debit.

### Two bugs found in passing, both worse than the feature

- **A stopped run lost its answer entirely.** `runs.py` caught `asyncio.CancelledError` on client
  disconnect — but a closed async generator raises **`GeneratorExit`**, also a `BaseException`,
  also invisible to `except Exception`. Both recorders were left unflushed with their sessions
  open, and the half-written answer was recorded as an error rather than a partial. Pinned by a
  test that stalls the proxy and fails if either exception is dropped.
- **`gc_checkpoints` over-collected.** It matched `DISTINCT r.thread_id WHERE r.created_at <
  cutoff`, so a conversation used daily was collected on the strength of the run that *started*
  it weeks ago. Now `GROUP BY … HAVING max(r.created_at) < cutoff`. Pre-existing and nearly
  invisible — a History tab is precisely what makes it reachable, and the symptom would have been
  an agent forgetting a chat the user was in the middle of.

### Where things live, and why

**History is per project** (`agent_id`, or `agent_id=none` for an unsaved canvas) and sits in the
Playground; **Media is workspace-wide** and sits in the left rail with All / Images / Audio tabs.
The split is deliberate: a transcript only means something next to its chat, while media is every
file the workspace ever produced. History originally shipped workspace-wide — on the theory that
pre-save conversations have a NULL `agent_id` and would vanish — and the consequence showed up
within minutes of real use: every project listed every other project's chats. The `none` sentinel
covers the unsaved case, and the recorder's upsert adopts a conversation into a project on its
next turn.

Audio rows lead with the caption plus a relative time and model; image tiles don't, because a
thumbnail identifies itself and a column of identical player pills does not.

### Two environment traps that look exactly like bugs

Both cost real debugging time and will again:

- **"History isn't saving"** = `alembic upgrade head` never ran locally. The recorder's
  best-effort contract means a missing table logs *one* warning and silently disables. Check
  `alembic current` first. (Production is automatic — `railway.json` has a `preDeployCommand`
  running the upgrade before the new container takes traffic, and `alembic` is a **runtime**
  dependency in `apps/api/pyproject.toml`, not a dev one, which is what makes that work.)
- **"Generated images don't appear in Media"** = `BLOB_READ_WRITE_TOKEN` unset. The image still
  *renders* in chat as a `data:` URI, which is what makes this read as a bug rather than missing
  config.

### Verified in production (2026-08-06)

`alembic_version = 0019` · a real Playground message appears in History and survives a reload ·
generated audio recorded and listed in the Media panel with its description · per-project
isolation confirmed. Pre-merge: **1515 python tests, 115 e2e**, zero failures, against a real
Postgres.

### Still open

- **Orphan sweep for pre-`0019` media** — see §3. Those objects have no row and are
  unrecoverable, the same shape as the pre-`0016` uploads.
- **Share-page uploads remain unattributable** (`workspace_id=None`), so they still survive
  account deletion — see the account-deletion section.
- **Media is not scoped per project.** The `/assets` endpoint already accepts `agent_id`, so it
  is a one-line frontend change if that ever becomes wanted.
- **TTS captions are capped at 60 characters** and are simply the opening of what was spoken. If
  a caption reads generically, the cause is upstream in what feeds the Voice node's text channel,
  not in the Media panel.

---

## 🟢 Account deletion + the downgrade path — DONE (2026-08-04), merged to main

Six PRs, all live: **#60** (`75fb5f7`) delete backend · **#61** (`56a4796`) Settings → Account ·
**#62** (`5826cbd`) Save/workspace polish · **#63** (`12fb927`) downgrade safety ·
**#65** (`688e5e3`) e2e hydration · **#66** (`f1dd26d`) capacity locking.

Two neighbouring paths that were never designed, only inherited: **deleting** an account, and
what happens when a Plus subscription **lapses**. Both had the same shape of bug — data destroyed
as a side effect of a billing state change, with no warning and no undo.

### Delete an account (#60, #61) — migration `0017`

Settings → Account was read-only. It now has three cards: editable profile (name + avatar,
uploadable via the existing `/uploads` endpoint), GitHub integration state, and Delete Account
behind a typed `delete my account`.

**Three things did not exist before this.** There was **no Stripe cancellation code anywhere in
`apps/api`** — deleting an account would have kept charging the card. `calypr_storage` exported
only `put_blob`, so every object orphaned permanently. And `resolve_account` is find-or-create,
committed on *every* request, so a database-only delete was silently undone by the next page load.

The shape: the request cancels Stripe **first** and 502s without touching anything if that fails
(an account deleted while its card keeps charging is the one outcome we can't ship), records what
must die in `account_purge`, and marks `deleted_at`. It **cascades nothing**. A nightly job does
the crossing, because Vercel Blob and LangGraph's checkpoint tables share no transaction with
Postgres — and both inline orderings lose a crash.

The resurrection guard lives **inside** the upsert (`WHERE deleted_at IS NULL` on `DO UPDATE`).
A check in front of the INSERT loses the race against a concurrent soft-delete; the upsert takes
the row lock before evaluating its predicate. It RAISEs SQLSTATE `CY001` rather than returning
NULL, because every caller reads a uuid as "proceed" and would fail **open**.

### What happens when Plus lapses (#63, #66) — migration `0018`

**Cancelling does not downgrade immediately, and that was already correct** — Stripe sets
`cancel_at_period_end`, the subscription stays `active`, and the account keeps Plus until the
period ends. Do not "fix" this again.

What happened *after* the drop was the problem. Three findings, in severity order:

1. **Run state was destroyed the same night.** `gc_checkpoints` derives its TTL from the plan
   *at collection time* and had no idea when that plan became true, so the instant a subscription
   lapsed everything 7–30 days old was already expired. `0018` adds `plan_changed_at` and a
   7-day grace window. Stamped **only on a real change**, or a redelivered webhook would extend
   retention forever.
2. **Credits were clawed back.** `grant_monthly` wrote `delta = target - current`
   unconditionally, so a downgraded account with 1,500 credits got a **negative ledger row
   labelled `grant`**. It now only ever tops up.
3. **Capacity was never reclaimed.** Caps were create-time only, so a lapsed account kept 3
   workspaces and 20 projects and could work in all of them forever — one month of Plus bought
   the capacity permanently. `locking.py` now makes the newest-over-cap read-only, derived from
   plan + `created_at` rank with nothing stored.

**The governing rule, in both halves: take back capacity, never data.** Locked rows stay
readable, exportable and **deletable** — deleting down to the cap is one of the two ways out, so
a lock that blocked it would be a trap with no exit.

### Three bugs found in passing, none in the feature being built

- **`authClient.deleteUser()` would have failed for almost every real user.** Better Auth gates it
  on session freshness (default 24h) unless a password is supplied — and GitHub OAuth users have
  no `credential` account, so that branch is unreachable. The client returns `{data, error}` and
  **does not throw**, so the failure was silent: account soft-deleted, session cookie left intact,
  user redirected while still holding it. Fixed with `session: { freshAge: 0 }` **and** an
  explicit error check. Invisible to 100/100 e2e, because nothing in dev or CI calls Better Auth.
- **The e2e suite raced hydration everywhere** (#65). Nearly every page is `"use client"` but
  still server-renders, so buttons ship in the HTML — visible, enabled, with testids — before
  `onClick` exists. Three spec files carried comments claiming `.react-flow__controls` guarded
  against this; it never did. The app now sets `<html data-hydrated>`. Four retry helpers deleted,
  ~50 more never written.
- **`GET /workspaces` now answers `{workspaces, plan, can_create}`.** Free caps at 1 workspace and
  every account already has "Personal", so "New workspace" could *never* succeed there — it
  collected a name and then refused it. Now a locked row linking to `/pricing`. `can_create` is
  decided by the API from `entitlements.LIMITS`, not re-derived in TypeScript where it would drift.

### Two testing lessons worth keeping

- **Mutation testing repeatedly caught weak tests.** A "delete is always allowed" test sent the
  delete from the *unlocked* workspace and passed even with `DELETE` gated. A credit clamp turned
  out never to be load-bearing (a guard below it did the work) and was removed rather than left as
  a second expression no test could pin.
- **Green locally, red in CI.** LangGraph's `checkpoints` tables are created by
  `AsyncPostgresSaver.setup()`, not Alembic, and only ever existed as a side effect of whichever
  test module entered the app lifespan first — alphabetically. A new module sorting before it
  found nothing. Now a session fixture in `conftest.py`; **verify DB tests against a scratch
  database, not a primed dev one.**

### Verified in production (2026-08-04)

`alembic_version = 0018` · Better Auth's `account` intact · account deletion exercised end to end
on a throwaway GitHub account, including `authClient.deleteUser()` · avatar upload and profile
save confirmed · locking exercised against a real over-cap account (correct 2 of 5 projects
locked, oldest kept; rename 402s; deleting one takes the count 2 → 1).

### Still open

- **Never manually verified:** a real **Stripe cancellation** through the delete path (prod keys
  are live — prefer a 100%-off coupon on a throwaway), and a real **blob delete** confirmed by the
  URL actually 404-ing. The test account is still inside its 7-day purge window; see
  `ACCOUNT-DELETION-RUNBOOK.md`.
- **Blobs we cannot delete — half fixed (2026-08-06, PR #73).** `_assets.py` (image/TTS output)
  now writes an `asset` row, and account deletion collects `asset.blob_url` and
  `orphan_blob.blob_url` alongside `upload.blob_url` through the same load-bearing
  `workspace.account_id` join. **Still unattributable:** share-page uploads (`workspace_id=None`)
  and any media generated before `0019`. The danger copy still says "uploads" rather than "all
  your files" — keep it that way until the share path is covered.
- **Usage tab renders `3 of 1`** as an ordinary meter when over-limit — honest, not styled as one.
- **Vercel *preview* deployments have been failing all day** (`Resource provisioning failed`,
  duration `?`) while **production deploys fine**. Proven environmental with a control branch: an
  empty commit off `main` fails identically. `build-test` is the real gate.
- **Never downgrade past `0017` in production** once anything has been deleted.

---

## 🟢 Multiple workspaces per account — DONE (2026-08-02), merged to main (PR #59, `8f429b7`)

**Live and verified in production.** Free gets 1 workspace / 3 projects / 500 MB; Plus gets
3 / 20 / 5 GB, **pooled across the account**. Railway-style switcher in the sidebar, new
**Templates** (placeholder) and **Usage** tabs, and the credits panel moved out of Settings →
Workspace onto Usage, next to projects and storage.

**Why it couldn't be UI-only.** `plan`, `stripe_customer_id` and `credit_balance_micro` lived on
the `workspace` row, so three workspaces would have meant three subscriptions and 3× the monthly
grant. Migration `0016` splits the tenant: an **account** pays, a **workspace** holds work. The
RLS GUC stays workspace-shaped, so every domain table's policy was untouched — only
`billing_account` and `credit_ledger` got a new predicate reaching up through
`workspace.account_id`.

**Account ids were reused from the workspace ids they replaced.** Load-bearing: in-flight Stripe
checkout sessions carry `client_reference_id = <workspace id>`, so they still resolve. Do not
change how account ids are assigned without draining checkout sessions first.

**The advertised project cap is now real.** `/pricing` promised "3 projects" since launch and
`PRICING-SPEC.md` §1 even specified the 402 — `create_agent` was a bare insert. Limits now live in
one `entitlements.LIMITS` table instead of constants spread across four modules, which is how the
gap survived.

### Two bugs found in passing, both worse than the feature

- **Threads were not bound to a tenant** (`dde932f`). `thread_id` was minted by the browser
  (`Math.random`) and passed straight to the LangGraph checkpointer, which resumes state by that
  id **with no check**. Verified end to end: two different accounts posting the same id landed in
  one conversation, both parties' messages in the same state. Hard to hit — ~57 bits of a value
  that is never shared — but the guess was the only thing in the way. Threads are now namespaced
  server-side (`ws:<workspace_id>:<suffix>`); the caller's value is only a suffix. Share links
  have no identity to bind to, so the server mints the suffix from `secrets` and returns it for
  the client to echo. `share.py` already carried a comment saying visitors must not resume each
  other's threads — the namespacing was there, the binding wasn't.
- **Runs were streaming unmetered and undebited.** `run_workspace` resolved the tenant in its own
  session and `/runs` never writes through it, so the find-or-create was rolled back,
  `RunRecorder` hit a foreign-key violation, logged "run metering disabled", and the run streamed
  free. **A new user's first runs cost nothing, silently.** Same root cause as the phantom-
  workspace fix in `3182d74`, which only covered `_resolve_workspace_id`; `run_workspace` had its
  own copy of the SQL. If a third resolver ever appears it needs the `commit()` too.

### Storage is displayed, not enforced — deliberately

The dominant consumer is LangGraph's checkpoint tables: created by `AsyncPostgresSaver.setup()`
**outside Alembic**, no `workspace_id`, reachable only through `run.thread_id`. Blob uploads wrote
no DB row at all before `0016` (the new `upload` table starts that record; earlier blobs are
unrecoverable). What actually bounds storage is a **per-plan retention window on run state** —
7 days Free, 30 Plus — swept nightly by `POST /internal/gc/checkpoints` via a Vercel cron
(`apps/web/vercel.json` → `/api/cron/gc`, `CRON_SECRET` set 2026-08-02). The GB figure is measured
on that same schedule and shown with its timestamp. **A byte-based 402 is deferred**, and needs a
"clear run history" lever first: today a user at 100% has no way down, because deleting a project
doesn't free its runs' checkpoints.

First production sweep: **1,145 rows across 56 expired threads** (checkpoints 937 → 578, blobs
589 → 366) with `run` rows untouched at 141 — history is kept, only state is reclaimed.

### The deploy-blocker that no test could catch

`0016` originally created a table called `account`. **Production already had one**: Better Auth
owns `user`, `session`, `account` and `verification` in the same Neon database, manages them
itself outside Alembic, and they are absent from any local database that has never run the web
app's auth. `account` is its OAuth-link table (`providerId`, `accessToken`, `password`). The
migration would have failed at Railway's `preDeployCommand` — fail-safe, but blocked.

Caught by **reading production row counts before merging**, not by 314 pytest + 91 e2e, all of
which were green against a database that didn't resemble production. Renamed to `billing_account`
(`a48f6d7`), and the local dev database was rebuilt with all four Better Auth tables present so
this class of collision is now catchable. Neon also keeps a *second* copy of those four in a
`neon_auth` schema — schema-qualify anything that inspects `information_schema`.

**Never name an Alembic table `user`, `session`, `account` or `verification`.**

### Verified in production (2026-08-02)

`alembic_version = 0016` · Better Auth's `account` intact with both rows · 3 workspaces → 3
accounts, no orphans, no NULL ledger rows · account ids reused (Stripe continuity) ·
**the Plus subscriber's plan, Stripe customer and 1,973,289 micro-credits all carried over** ·
19 agents / 141 runs / 16 ledger rows present · internal GC endpoints 401 without a valid key ·
**cross-account workspace claims rejected on live accounts** (A claiming B's workspace, and a
random uuid, both fall back to A's own).

### Deliberately not done

- **Storage 402** — see above; needs the "clear run history" lever first.
- **Moving projects between workspaces.** Pooling the project quota already makes this a pure
  relocation with no cap check that can fail. When it lands: share links move with the agent
  (a live URL scoped to it), run history does **not** (it belongs to the workspace that spent the
  credits — which is why `credit_ledger.workspace_id` was kept as provenance).
- **Per-workspace usage + private/public visibility.** The per-workspace breakdown is already
  unlocked by that same provenance column. The visibility toggle has a trap: the share path
  bypasses the tenant GUC via the `SECURITY DEFINER` functions `share_agent_name` /
  `claim_share_run`, so the predicate must go **inside those functions** — gating link *creation*
  in the router would leave links minted while public still resolving after a flip to private.

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
