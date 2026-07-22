# Calypr — 6-Month Roadmap

**Date:** 2026-06-23 · **Horizon:** Months 1–6 (extends the 90-day plan in
[`WEDGE-PLAN.md`](./WEDGE-PLAN.md)) · **Status:** DRAFT · **Author:** co-founder mode

> Co-founder roadmap, downstream of [`OFFICE-HOURS.md`](./OFFICE-HOURS.md).
> ICP = **AI engineer** (agency/consultant + internal platform flavor). Bet =
> **stay-and-extend runtime**. Model = **open-core** (Approach C: OSS the DSL,
> paid canvas+runtime). Beachhead = **ecommerce-adjacent AI engineers**, used to
> validate, not to narrow the product.

---

## North Star — the destination (18-month+)

Calypr becomes **the agentic layer**: the platform where AI engineers build
agent-powered apps, and anyone can buy, run, and tweak them. "A website marketplace,
but for agent-powered apps." Each unit is a full app that ships with (a) a configurable
agentic backend built on the canvas and (b) a tweakable front-end UI design system. The
AI engineer is the **supply side** (creator); the person who wants the app is the
**demand side** (buyer).

This is the destination. It is **not** the near-term plan. A two-sided marketplace and a
front-end app builder are oceans, and both are unreachable unless the core is proven
first. The north star changes the *ambition*, not the *sequence* — if anything it makes
the round-trip canvas and the hosted runtime MORE load-bearing, because every rung below
depends on them.

### Vision ladder (how today's wedge climbs to the north star)

| Rung | What exists | Who it's for |
|------|-------------|--------------|
| **0 — today** | Agent design canvas + round-trip code + hosted runtime | AI engineer builds one agent |
| **1** | Stay-and-extend proven; engineer ships a running agent to end users (share-to-test → embed / per-agent API) | AI engineer + their client |
| **2** | Templates/packages of agents (the workflow-template layer) | AI engineers reuse each other's work |
| **3** | Agents ship WITH a tweakable UI — the "app" unit emerges | AI engineer packages an app, not just an agent |
| **4** | Marketplace of agent-powered apps (two-sided: creators + buyers, payments) | Creators sell; anyone buys |
| **5** | Calypr as the default agentic layer under many apps | Platform |

The 6-month roadmap below covers **Rungs 0–1** and sets up **Rung 2**. Rungs 3–5 are
gated on data and traction, not on a date. The front-end/UI dimension (Rung 3) is the
biggest scope addition and must not start until Rungs 0–1 are proven — a UI builder is a
whole product (Webflow/Framer territory), and front-loading it pre-validation is the
scope-expansion that kills solo founders.

---

## 0. The honest co-founder note up front

Office hours six hours ago ended with: *"The strategy is settled. The only thing
missing is evidence. Do not write another strategy doc."* So here is the deal with
this document:

**This is not a feature wishlist. It is a sequence of go/no-go gates.** Month 1 is
mostly validation with build running in parallel *to serve* validation. Every month
has a kill condition. If you grind through this like a checklist of features to ship,
you will have repeated the strategy-churn pattern (4 positions in 5 days) with extra
steps. The whole point is to falsify the bet cheaply, then concentrate on what
survives.

Two facts reorder the plan, and the second one rewrites it:

1. **No demand is validated.** Zero users, zero design partners, zero paying
   customers. Conviction is real but it is a reasoned bet with founder-as-user
   ecommerce pain underneath. Warm, not hot.
2. **The core bet is half-built.** `services/compiler/src/calypr_compiler/compile.py`
   compiles GraphSpec → LangGraph (forward). `services/codegen` generates readable
   Python from the spec (forward). **There is no reverse path: nothing parses edited
   code back into a GraphSpec.** Today a user who drops into code *cannot get back to
   the canvas.* The "no-ceiling" promise is, right now, a promise the product cannot
   keep. This is the existential engineering risk and it owns Month 2.

---

## 1. Current state (grounded in the repo, not vibes)

**Built (Phases 0–5, on `main`):**
- Canvas: `apps/web` (Next.js + React Flow), landing page, Better Auth (`apps/web/src/lib/auth.ts`, GitHub OAuth + dev fallback).
- API: `apps/api` (FastAPI), routers `agents` + `runs`, Postgres + pgvector, Alembic baseline + agents migrations.
- DSL: `packages/dsl` (Pydantic GraphSpec → generated TS via `scripts/gen-ts.mjs`).
- Nodes: `packages/nodes` (registry, capability nodes, agent types).
- Services: `compiler` (GraphSpec → LangGraph), `codegen` (GraphSpec → readable Python), `runtime`, `model`.
- Engine features: RAG ingestion, tools + ReAct, agent types + conditional control flow, Reflexion revise loop, per-node models.

**Missing (the gaps that shape the roadmap):**
- **Reverse round-trip (code → canvas):** does not exist. The thesis, unbuilt.
- **Cost metering / token usage / margin tracking:** zero code. The #1 business risk.
- **Eval hooks:** zero code. Your reliability differentiator, unbuilt.
- **Billing:** no Stripe, no tiers.
- **Code-drop + ceiling-event instrumentation:** the events you live or die by, not wired.
- **Share-to-test:** the viral loop, not built.
- **Per-tenant isolation beyond auth:** RLS not verified.

---

## 2. Operating principles (non-negotiable)

1. **Validation gates ownership.** No growth spend, no public launch, no marketplace
   until the prior gate passes.
2. **The one bet is round-trip code quality.** If the generated code isn't mergeable
   and the reverse path doesn't survive edits, the company is a demo. Resource it
   like the core product, because it is.
3. **Open-core, not OSS-everything.** Open the trust-building artifact (DSL + codegen),
   charge for the experience around it (canvas, runtime, copilot, collaboration, evals).
4. **Gross margin per run is a hard gate.** Meter and cap from day one; route free
   generation to a cheap model; never ship an uncapped "build me a system" prompt.
5. **Stay-and-extend, not export-and-leave.** The runtime and collaboration are the
   money. Code ownership is the trust layer that keeps people, not the door out.
6. **No new strategy docs.** Execute this one. Revise it only at a gate.

---

## 3. Month-by-month

### Month 1 — Prove the artifact + run the assignment
**Goal:** Find out if the code is good enough and if anyone cares.

**Validate (this is the main work):**
- **Week 1–2:** Run the **blind code-quality panel** (`WEDGE-PLAN.md` line 184, the
  action you already committed to and have not done). 5–8 senior engineers review
  generated code with no context. Target ≥ 70% "would-merge," ≥ 4/5 mean.
- Write down the **one name** you said you could name. Find **nine more**
  ecommerce-adjacent AI engineers. Book **five calls**. Watch each build one real agent.

**Build (in parallel, only what serves validation):**
- **Cost metering:** per-run / per-agent / per-tenant token count + $ — `services/runtime` + `apps/api`. Non-negotiable, instruments from day one.
- **Eval hooks:** pass/fail per run against a golden set per template — `services/compiler`.
- **Code-drop + ceiling-event instrumentation:** the two events that decide the thesis.
- **Share-to-test:** let a design partner show a prototype to a stakeholder via link — the viral seed.

**Approach C OSS prep (no launch yet):**
- License decision (Apache-2.0 vs AGPL-3.0). Standalone README + one killer demo for `packages/dsl`. Hold the public launch for Month 3.

**Gate (end M1):**
- ≥ 70% would-merge on the panel **AND** ≥ 10 design partners with a real agent running **AND** cost/eval/code-drop instrumented.
- **Kill:** code quality < 70% → stop all growth work, fix generation. No exceptions.

---

### Month 2 — Build the reverse round-trip + prove no-ceiling retention
**Goal:** Make the thesis technically true, then find out if users stay when they hit the wall.

**Build (the existential track):**
- **Reverse round-trip: code → GraphSpec.** Start week 5. This is the make-or-break.
  - **Constraint the surface:** parse *generated* Python back to spec, not arbitrary Python. Keep the editable surface inside a known, versioned shape so the round-trip is tractable and testable.
  - Bidirectional property tests: spec → code → spec equals original (within an equivalence relation you define).
  - Target round-trip survival ≥ 95%.
- Ship **3–4 templates spanning simple→complex** (single-tool → RAG → multi-agent) so users naturally reach the ceiling and discover code-drop.

**Validate:**
- Closed beta in earnest. Track the **ceiling event:** at the wall, do they (a) drop into code and continue, or (b) churn? This ratio is the whole thesis.
- Weekly design-partner interviews: where did they hit the wall, did code save them, would they have left otherwise?

**Gate (end M2):**
- Reverse round-trip works for the core node set **AND** ≥ 50% of ceiling-event users drop into code and stay 14+ days **AND** 30-day agent retention ≥ 40% for the cohort.
- **Kill:** ceiling resolution < 50% → the handoff UX is broken or the segment doesn't want code. Diagnose before any further build.

---

### Month 3 — Prove willingness to pay + OSS the DSL (end of the WEDGE 90 days)
**Goal:** Confirm the segment pays; let the data pick the sub-segment to dominate.

**Build:**
- **Paid tiers** (hybrid seat + usage). Stripe integration in `apps/api`. Charge real money — willingness to pay is the only honest signal.
- **Public OSS launch of the DSL + codegen** (the low-stakes, redo-able one). Show HN. The "a versioned graph spec → LangGraph" post. This is your credibility + top-of-funnel layer.

**Validate:**
- Segment retention + conversion by ICP sub-type: agencies vs product teams vs solo technical founders. One will over-index.
- Stand up the agency motion as a channel test: can one agency deploy Calypr agents to ≥ 3 clients?

**Gate (end M3 — the WEDGE go-to-G1 bar):**
- ≥ 25 paying workspaces **AND** positive gross margin per run **AND** ≥ 1 segment converting ~3× the others.
- **Kill:** < 25 paying OR negative margin OR no segment separation → do not scale; iterate the wedge or revisit ICP. If 30-day retention is flat everywhere, it's a product-quality problem, not a market problem.

---

### Month 4 — Harden the moat + codify the open-core boundary
**Goal:** Make the thing that's hard to copy harder, and make the business boundary explicit.

**Build:**
- **Open-core boundary, in code:** open = `packages/dsl` + `services/codegen` + `packages/nodes`; paid = canvas, hosted runtime, copilot depth, collaboration, evals dashboard. License + contribution policy enforced.
- **Reliability:** multi-provider failover (OpenAI ↔ Anthropic ↔ Google), circuit breakers, retries + backoff, idempotency, per-tenant rate limits. 99.9% target with error budgets.
- **Round-trip hardening:** expand the supported node set; bidirectional property tests across the whole registry. The moat deepens.
- **Iterative copilot (paid):** watches runs, debugs, explains, self-heals, extends an existing graph. This is the thing people actually pay for (`WEDGE-PLAN.md` §2) — one-shot generation is the hook, conversational refinement on a live graph is the product.

---

### Month 5 — The NRR engine, picked by data
**Goal:** Drive seat expansion + stickiness. Build the *one* of these the data points at, not both.

**Data-driven fork:**
- If design partners asked for co-edit / versioning / review → **collaboration.** Ship **async versioning first** (GitHub-style branches + review). Real-time multiplayer **only** if engineers explicitly demand it — async is cheaper and may be enough.
- If they hit AI caps and wanted more → **deepen the copilot** instead.

**Build (whichever fork):**
- Collaboration: async branches, review, per-agent REST API. The NRR / seat-expansion engine.
- Expand templates to **6–8** now that retention mechanics exist.

---

### Month 6 — Concentrate + set up the next bet
**Goal:** Double down on the winning sub-segment; decide what's next from data, not hope.

**Build / decide:**
- **Concentrate:** messaging, templates, and onboarding speak to the winning sub-segment. Runtime stays open underneath.
- **Pick the next bet from data:** marketplace (Rung 4 / G2 of `MVP.md`) **vs** vertical 2 **vs** an early Rung-3 "app packaging" probe. The Rung-3 probe (one agent shipped *with* a tweakable UI shell, hand-built, not a general UI builder) is the only vision-ladder work that's cheap enough to try in Month 6 — and only if buyer-side demand signal from design partners says they want an *app*, not just an agent. Do not start a general UI/design-system builder on this horizon.
- **Marketplace rule (unchanged):** two-sided marketplace = Rung 4, gated on PLG traction. No marketplace scaffolding without community pull.
- **SOC 2 Type I kickoff** if enterprise pipeline warrants it. PLG-first lets it wait, but start the clock so it never blocks a deal.
- Prepare a real **case study** from the strongest design partner. One story > ten features.

---

## 4. Cross-cutting engineering backbone (runs all 6 months)

| Track | Why it's permanent | Owner cadence |
|------|-------------------|---------------|
| **Round-trip code quality** | The bet. The whole company. | Continuous, dedicated track |
| **Cost & margin control** | #1 business risk; gate everything on positive gross margin | Continuous |
| **Evals** | The reliability differentiator; regression on every graph change | Continuous |
| **Observability** | OpenTelemetry end-to-end; per-run debug traces in the UI | M3 onward |
| **Per-tenant isolation** | RLS + automated isolation tests | M2–M4 |
| **LangGraph firewall** | Keep the compiler behind an interface; minimize LangChain surface | Continuous |

---

## 5. Anti-roadmap — what we are explicitly NOT doing

- **No general front-end / UI design-system builder** on this 6-month horizon. That's
  Rung 3, gated on Rungs 0–1 proving out. A tweakable-UI app builder is a full product
  (Webflow/Framer territory); starting it pre-validation is the scope-expansion that
  kills solo founders. The only UI work allowed is one hand-built app shell for a gated
  Month-6 Rung-3 probe.
- **No two-sided agent-app marketplace** before PLG traction. It's Rung 4 / `MVP.md`
  Workstream C, the hardest cold-start in software. Don't push one nobody asked for.
- **No real-time multiplayer** before async versioning, and only if engineers ask.
- **No vertical 2** (Sales/RevOps) before the ecommerce beachhead concentrates.
- **No enterprise tier** (SSO/SAML, dedicated infra) before there's enterprise pipeline.
- **No general Python parser** for round-trip. Constraint the editable surface; a general parser is an ocean, not a lake.
- **No new strategy docs.** Execute. Revise only at a gate.

---

## 6. Risks & kill signals (watch weekly)

| Signal | What it means | Action |
|--------|--------------|--------|
| **Reverse round-trip proves intractable** | The thesis dies. Existential. | Pivot to scoped round-trip (a constrained editable region) or re-scope the "no-ceiling" claim to "export-and-extend." Honest pivot, not a quiet walk-back. |
| **Code-drop rate near zero** | Users don't value the code; the wedge is false. | Re-scope or change wedge. |
| **High ceiling-event churn** | The code handoff UX is broken. | Fix the handoff before any growth. |
| **Negative gross margin per run** | Pricing/cost problem. | Don't scale; smart routing + premium tiers + cap free tier. |
| **Flat 30-day retention everywhere** | Product-quality problem, not market. | No positioning fixes this. Fix the product loop. |
| **AI-built agents churn faster than hand-built** | The copilot produces impressive garbage. | Fix generation quality before charging for the copilot. |

---

## 7. The single most important thing

**Month 1's blind code panel + Month 2's reverse round-trip.** Everything else is
commentary. If the code isn't mergeable and the round-trip doesn't survive, no amount
 of marketplace, OSS launch, or template-store work will save the company. If both
 pass, you have a real wedge and the rest of this roadmap is execution. Go run the
 panel this week.
