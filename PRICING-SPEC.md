# Calypr — Pricing Model & Credits Spec (Free / Plus)

**Date:** 2026-07-02 · **Status:** SPEC for implementation · Extends
[`MVP-EXECUTION-PLAN.md`](./MVP-EXECUTION-PLAN.md) Weeks 2 (metering) and 9–10 (Stripe +
pricing surface); consumed by the assistant in [`AI-ASSISTANT-SPEC.md`](./AI-ASSISTANT-SPEC.md).

## 1. Plan matrix (decided)

| | **Free** | **Plus — $20/mo** |
|---|---|---|
| Projects (agents) | **3** | **20** |
| **Code export** — edit the generated Python + Apply to canvas (`POST /parse`) | ✗ | **✓** |
| Node LLM calls (canvas runs) | **BYOK only** — user's own OpenAI/Moonshot/DeepSeek key; 0 credits consumed | Platform keys on all 3 models, metered in credits; **BYOK still allowed** (0 credits) |
| AI chatbot (assistant) | **100 credits/mo**, chatbot-only, **DeepSeek-routed** (~15–20 graph generations) | Full credit pool, any of the 3 models |
| Monthly credit grant | 100 (chatbot-only) | **2,000** (shared across node runs + chatbot) |
| Rollover / top-ups | none v1 | none v1 (top-up packs = fast-follow) |
| Share links | run-capped per link (existing `run_cap`) | run-capped; runs debit the owner's credits (or BYOK) |

One credit system, two spenders: **canvas node runs** and the **AI chatbot**. Both already
flow through the same `usage` event pipeline (`services/model` → `services/runtime` →
`apps/api/routers/runs.py`, and `/assist` per its spec), so one ledger meters both.

**Code export (added 2026-07-22, closed-product pivot).** The one Plus line that isn't capacity:
the product is closed, so taking your graph out as Python is what a paid plan buys. Enforced
server-side by `deps.require_code_export` on `POST /parse` (402 `{reason: "plan", feature:
"code_export"}`), not just hidden in the UI; `beta` workspaces keep it, since we don't take a
shipped feature back off the cohort already using it.

**Image + Voice credit rates — RESOLVED 2026-07-23.** This spec never listed them, which read
as "two node types can't be metered". It was a *documentation* gap, not a pricing one: credits
are derived from the USD table in `pricing.py` (`credits_for` = `cost_usd × 500`), and both were
already priced there — Image is token-billed on image-OUTPUT tokens, and TTS records its
character count in the `input_tokens` field, so "per 1M characters" flows through the same
arithmetic. Deriving rather than keeping a second hand-maintained credit table is what makes the
5× margin hold on **every** model automatically; a test asserts it across the whole table.

What that buys on the 2,000-credit Plus grant, at today's rates:

| Usage | Credits | Plus grant covers |
|---|---|---|
| One 1024×1024 image (`gpt-image-2`) | ~16 | ~125 images/mo |
| 1,000 characters of speech (`gpt-4o-mini-tts`) | 7.5 | ~266k characters/mo |
| A chat turn (`gpt-4o-mini`, 1k in / 500 out) | ~0.22 | ~9,000 turns/mo |

**Still open — read-only code viewing.** The Code tab renders generated Python to *everyone*
today (a `<pre>`; `POST /codegen` is unauthenticated). Only editing + Apply-to-canvas is gated.
Decide before Plus goes on sale whether viewing/copying is part of the free tier (it doubles as
the "no lock-in" reassurance that sells the plan) or moves behind it too — this table describes
the former.

## 2. The credit unit (the core design decision)

**1 credit = $0.002 of model COGS = $0.01 retail.** Margin multiplier **M = 5×** is a
constant, applied uniformly per token direction:

```
credits_per_1M_tokens = provider_usd_per_1M × M / CREDIT_RETAIL_USD
                      = provider_usd_per_1M × 5 / 0.01
                      = provider_usd_per_1M × 500
```

Because rates derive **per direction** (input and output separately) from the provider
price sheet, the 5× margin holds on *every* token regardless of usage mix — this matters
because output prices are wildly asymmetric (Kimi output is ~10× DeepSeek output). A
single "blended multiplier" would under-charge output-heavy workloads; we only use blended
numbers for display.

### Launch models & credit rates (prices verified 2026-07-02 — re-verify at build)

| Model (id prefix) | Provider $/1M in | $/1M out | **Credits/1M in** | **Credits/1M out** | Display tier |
|---|---|---|---|---|---|
| `deepseek-v4-flash` (default) | $0.14 | $0.28 | **70** | **140** | **1× — Fast** |
| `gpt-4.1-mini` | $0.40 | $1.60 | **200** | **800** | **~4× — Balanced** |
| `kimi-k2.5` | $0.60 | $3.00 | **300** | **1,500** | **~7× — Frontier** |

Display tiers use a 3:1 input:output blend ($0.175 / $0.70 / $1.20 per 1M blended →
1 : 4 : 6.9). Marketing copy: "1× / 4× / 7× credits."

**What 2,000 Plus credits buy** (blended): ~22M DeepSeek tokens, ~5.7M GPT-4.1-mini
tokens, or ~3.3M Kimi K2.5 tokens per month. Worst-case COGS of the grant is $4.00 by
construction (uniform 5×) → **80% gross margin** on the $20 plan, satisfying the
ROADMAP-6M "positive gross margin per run" gate. Free-tier worst-case COGS: 100 credits ≈
$0.20/user/mo.

### Price-drift caveats (why rates live in one table, §3)
- These are July-2026 list prices; DeepSeek/Kimi/OpenAI all repriced within the last six
  months (Kimi legacy K2 was EOL'd 2026-05-25 — do not launch on `kimi-k2`, use `k2.5`).
- All three providers discount **cached input** heavily (DeepSeek −98%, Kimi ~−85%,
  OpenAI −75%). v1 charges the cache-miss rate (conservative, protects margin); passing
  cache savings through is a Phase-2 optimization once `usage` events carry cached-token
  counts.

## 3. How we tweak token→credit cost (the engineering mechanism)

Single source of truth — extend the `pricing.py` module already planned in Week 2
(`apps/api/src/calypr_api/pricing.py`):

```python
CREDIT_RETAIL_USD = 0.01          # $ value of 1 credit to the user
MARGIN_MULTIPLIER = 5.0           # uniform platform margin
MICRO = 1_000                     # ledger stores micro-credits (integer math)

MODEL_PRICES: dict[str, ModelPrice] = {   # USD per 1M tokens, cache-miss rates
    "deepseek-v4-flash": ModelPrice(input=0.14, output=0.28),
    "gpt-4.1-mini":      ModelPrice(input=0.40, output=1.60),
    "kimi-k2.5":         ModelPrice(input=0.60, output=3.00),
}

def credit_rate(model_id) -> CreditRate:      # derived, never hand-set
    p = MODEL_PRICES[resolve(model_id)]
    k = MARGIN_MULTIPLIER / CREDIT_RETAIL_USD  # ×500
    return CreditRate(per_1m_in=p.input * k, per_1m_out=p.output * k)

def debit_micro(model_id, in_tok, out_tok) -> int:
    r = credit_rate(model_id)
    return ceil((in_tok * r.per_1m_in + out_tok * r.per_1m_out) * MICRO / 1_000_000)
```

Tweaking levers, in order of bluntness:
1. **Provider repriced** → edit `MODEL_PRICES`; credit rates shift automatically, margin
   invariant preserved.
2. **Margin change** (e.g. promo, or margin gate failing) → `MARGIN_MULTIPLIER`, global.
3. **Per-model strategic override** (e.g. loss-lead the default model) → optional
   `CREDIT_RATE_OVERRIDES: dict[str, CreditRate]` checked before derivation; each entry
   must carry a comment justifying it.
4. **Hotfix without deploy** → env-var JSON override (`CALYPR_PRICING_OVERRIDES`) parsed
   at startup; keep it empty in normal operation.

Guardrails: a pytest asserts `credit_rate(m) ≥ MODEL_PRICES[m] × 1/CREDIT_RETAIL_USD`
(i.e. effective margin ≥ 1× — we never sell tokens below cost) for every model including
overrides; unknown model ids fall back to the most expensive rate (fail-closed, not
fail-free). Calendar note: re-check the three provider price pages monthly until volume
justifies automation.

## 4. Data model (Alembic — the Week-9 billing migration, `0010_billing.py`)

> Numbering corrected 2026-07-22: this section was written against `0006_billing.py`, but the
> tree is already at `0009_assistant_model.py`. Note also that `workspace.plan` (`0008`) and
> `provider_key` (`0007`, Fernet + `CALYPR_VAULT_KEY` — *not* the AES-GCM/
> `CALYPR_KEY_ENCRYPTION_KEY` this section describes) have **already shipped**, so the billing
> migration adds only the Stripe + ledger columns below.

- `workspace` += `plan` (`free|plus`, default free), `stripe_customer_id`,
  `credit_balance_micro` (cached; ledger is truth), `grant_cycle_anchor` (date).
- **`credit_ledger`**: id, workspace_id (RLS pattern from `0001_baseline.py`),
  `delta_micro` (int, + grant / − debit), `kind` (`grant|debit|topup|adjust`),
  `source` (`run|assist`), `ref_id` (run id), `model`, `created_at`.
  Balance = `sum(delta_micro)`; update the cached column in the same transaction.
- **`provider_key`** (BYOK): workspace_id, `provider` (`openai|moonshot|deepseek`),
  `encrypted_key` (AES-GCM, master key from env `CALYPR_KEY_ENCRYPTION_KEY`; never
  returned by any API — write-only, list shows last-4), unique (workspace_id, provider).
- Grants: Plus → on Stripe `invoice.paid` webhook; Free → lazily on first assist call in a
  new calendar month (no cron needed).

## 5. Enforcement points (all in `apps/api`)

| Surface | Check | On failure |
|---|---|---|
| `POST /agents` (`routers/agents.py::create_agent`) | project count < plan cap (3/20) | 402 `{reason: "project_cap", plan, cap}` |
| `POST /runs` (`routers/runs.py::create_run`) | per Agent-node model: workspace BYOK key exists → run with it, **0 credits** (still meter tokens, `source="byok"` on the run row); else platform key path → plan must be `plus` (Free has no platform node runs) AND `credit_balance > 0` | 402 `{reason: "credits" \| "byok_required"}` |
| `POST /assist` | Free: DeepSeek forced + chatbot grant balance; Plus: any model + pool balance | 402 `{reason: "credits"}` |
| `POST /share/{token}/runs` | owner's credits/BYOK, plus existing per-link `run_cap` | 4xx as today |

Debit happens **post-run** from the accumulated `usage` events (same hook that writes
`run`/`run_usage` in Week 2), one ledger row per run/assist call. A run in flight when the
balance hits zero completes (bounded overshoot — `max_tokens` caps it); the *next* call
402s. Mixed graphs (some nodes BYOK, some platform) debit only platform-key node usage —
per-node `model` is already in the enriched usage payload.

BYOK plumbing: `model_for()` (`services/model/factory.py`) gains an optional
`api_key`/`base_url` override, resolved in the API layer from `provider_key` before
invoking the runtime — key material never enters the GraphSpec or the generated code.

## 6. Pricing surface (web)

- **`/pricing` page**: two-column Free/Plus with the plan matrix above; per-model credit
  badges (1×/4×/7×).
- **Upgrade modal** (the "pricing modal"): a single `<UpgradeDialog reason=… />` component
  triggered by any 402 (`project_cap` → "You've used 3 of 3 free projects";
  `credits` → usage bar + "Plus includes 2,000 credits/mo"; `byok_required` → "Add your
  API key or upgrade"). One component, reason-specific copy; CTA → Stripe checkout
  (Week 9) or Settings → API keys.
- **Settings**: Billing tab (plan, credit meter with per-model breakdown from `run_usage`,
  manage subscription) + **API keys tab** (BYOK add/remove, masked, per-provider).
- Canvas ConfigPanel: model dropdown shows the credit tier badge next to each model, and a
  "your key" chip when a BYOK key covers that provider.
- PostHog: `paywall_shown` (reason), `upgrade_clicked`, `byok_key_added`, `credits_exhausted`.

## 7. Tests ("done" gates)

- pytest: margin invariant across all models + overrides; `debit_micro` integer math
  (ceil, no float drift); ledger balance = cached balance under concurrent debits;
  Free assist forced to DeepSeek; unknown-model fail-closed rate.
- API tests: 3-project cap → 402; Free platform-key node run → 402 `byok_required`; BYOK
  run debits 0 but writes metered `run` row; credit exhaustion mid-month → 402 with
  correct reason; monthly lazy grant resets Free chatbot allowance.
- Playwright: hit the free project cap → upgrade modal renders; add a (fake) BYOK key →
  node run succeeds keylessly via the fake provider path.

## 8. Explicitly not in v1

Top-up packs and credit rollover; passing provider cache-hit discounts through to credit
rates; annual billing; team/seat pricing (Month-5 collaboration fork); per-agent spend
limits; a metered "Pay as you go" tier; auto-model-routing by price ("smart routing" is
the ROADMAP-6M margin lever if the gate fails — the override table in §3 is where it
plugs in).

## 9. Unit economics & loss exposure (the math)

All worst-case numbers assume 100% credit burn. 1 credit = $0.002 COGS by construction
(§2), and COGS-per-credit is the same on every model because rates derive uniformly at 5×.

### Free user — what one costs

| Scenario | Model COGS / month | / year |
|---|---|---|
| **Worst case** (burns all 100 chatbot credits) | 100 × $0.002 = **$0.20** | **$2.40** |
| Typical (~25% burn) | ~$0.05 | ~$0.60 |
| **Dormant** (never opens the assistant that month) | **$0.00** | $0.00 |

- Dormant = $0 because grants are **lazy** (§4: granted on first assist call of the
  calendar month) and don't roll over — a signed-up-but-inactive "subscriber for a year"
  costs literally nothing in model spend.
- Free **node runs are BYOK-only** → $0 to us, including runs through their share links.
- Marginal infra per free user (rows in Neon, a few KB of JSONB graphs) is ~pennies/year.

**So: a free user subscribed for a year costs at most ~$2.40, typically well under $1,
and $0 if inactive.**

### Plus user — do they cost us? Yes, but they can't go negative

| Item | Worst case / month |
|---|---|
| Revenue | +$20.00 |
| Model COGS (2,000 credits fully burned) | −$4.00 |
| Stripe fee (~2.9% + $0.30) | −$0.88 |
| **Contribution margin** | **+$15.12 (≈76%)** |

A Plus user is cash-positive **by construction**: the credit grant's maximum COGS ($4) is
fixed below the price ($20), BYOK usage costs us nothing, and there's no unmetered path.
Residual leak vectors, all bounded: (a) the post-run debit overshoot (§5) — one run past
zero, capped by `max_tokens`, worth ~$0.01; (b) provider price *increases* not yet
reflected in `MODEL_PRICES` — covered by the monthly price check + margin-invariant test
(§3); (c) refunds/chargebacks — standard Stripe Radar hygiene.

### How many free users can we carry?

- **One Plus subscriber funds ~75 worst-case free users** ($15.12 ÷ $0.20), or ~300 at
  typical burn.
- **Pre-revenue:** max worst-case *active* free users = monthly loss budget ÷ $0.20.
  ($50/mo budget → 250 active free users; realistic capacity ~4× that at typical burn.)
- **Post-revenue rule of thumb:** keep free-tier model COGS ≤ 20% of MRR. At $0.20
  worst-case per active user this reduces to: **max active free users ≈ MRR in dollars**
  ($500 MRR → ~500 active free users, worst case).
- In practice the binding constraint arrives long after the closed-beta phase (~10–25
  design partners per ROADMAP-6M) — don't build signup caps yet.

### The actual safety net (build this, not a signup cap)

A **platform-wide monthly spend kill switch**: `CALYPR_PLATFORM_SPEND_CAP_USD` (start:
$100). Checked in the §5 enforcement points against
`SELECT sum(cost_usd) FROM run WHERE source != 'byok' AND month = current`. When tripped,
platform-key runs and assist calls 402 for everyone (BYOK keeps working), and you get an
alert. This bounds the worst month to a number you chose in advance, no matter what user
counts, bugs, or abuse do — per-user caps are margin tuning; this is the loss firewall.

## Sources (prices as of 2026-07-02)

- DeepSeek: [official pricing docs](https://api-docs.deepseek.com/quick_start/pricing-details-usd/), [CostGoat Jul-2026 guide](https://costgoat.com/pricing/deepseek-api)
- Kimi/Moonshot: [TokenMix K2-family pricing](https://tokenmix.ai/blog/kimi-k2-api-pricing), [OpenRouter K2.5](https://openrouter.ai/moonshotai/kimi-k2.5)
- OpenAI: [official API pricing](https://developers.openai.com/api/docs/pricing), [PricePerToken GPT-4.1-mini](https://pricepertoken.com/pricing-page/model/openai-gpt-4.1)
