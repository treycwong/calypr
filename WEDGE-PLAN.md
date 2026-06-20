# Calypr — The "No-Ceiling" Wedge

### 90-Day Validation Plan & Metrics

**Date:** 2026-06-20
**Thesis in one line:** A visual agent builder whose canvas compiles to *real, good, version-controlled code that round-trips* — so builders never hit the wall that makes them churn off every other no-code tool.

**Three altitudes:** **prompt → canvas → code.** AI builds it (speed), the canvas lets you see and trust it (inspect/edit), the code lets you own it (no lock-in). One artifact, three views. Competitors have one or two of these; almost none connect all three.

> **This is the governing strategy doc for Calypr.** It supersedes the E-Commerce
> positioning in `MVP.md` and the e-commerce-flavored templates in `CLAUDE-PLAN.md`.
> The ICP is the **AI engineer**; the runtime stays open. See `CLAUDE-PLAN.md` for the
> build plan / architecture and the realigned phase roadmap.

---

## 1. Positioning

**The one-liner (external):**
> Build agents on a canvas. Own them as code. No ceiling, no lock-in.

**The axis of "better":** Every no-code agent tool (Zapier Agents, Lindy, Gumloop) and every model-lab builder (AgentKit and friends) is a black box. Users outgrow it, hit something it can't express, and churn to raw code. Calypr's bet is that the canvas, the versioned DSL, and the generated code are **one artifact at three altitudes** — so the moment of "this got too complex" becomes *the moment you reach for the code*, not the moment you leave.

**ICP (one primary persona — the AI engineer):** the person who builds and ships agents.
- AI / product engineers building agents at startups and product teams
- Technical founders and internal-tools / platform teams who want to move faster than raw LangGraph but refuse to be locked into a black box
- Agencies / MSPs whose engineers build agents for clients (a channel, not just a customer)

**Who they collaborate with (not new buyers — collaborators around the primary user):** other engineers (co-build, review, versioning) and non-technical stakeholders/PMs who *test* a prototype via a shared link. The product has one creator seat — the AI engineer — and everyone else orbits it.

### Vision & category
**"Figma for agentic design" — read correctly.** Figma won not by being visual but by (a) multiplayer and (b) collapsing the boundary between roles into one source of truth. For a single technical persona that translates to **"Figma's multiplayer × GitHub's versioning, for agents":** engineers co-build and review on a shared, versioned artifact, and ship runnable prototypes others can test. Use the Figma line *externally* (it's a great narrative); internally, the moat is round-trip code + evals + a real runtime + collaboration as the source of truth — not a pretty canvas.

**What this is NOT:** an escape-hatch "export and leave" feature. That version's success metric is churn. We are building **stay-and-extend**: bidirectional canvas ⇄ code on our runtime.

---

## 2. The AI copilot layer (prompt → build)

The top altitude: a chat interface where a user describes what they want ("build me a multi-agent system that triages support tickets, drafts replies, and escalates refunds") and the AI assembles the workflow on the canvas.

**Monetization — gate depth, not the generator.** Prompt-to-workflow is becoming table stakes (n8n, Gumloop, Zapier, the model-lab builders all ship it). The AI builder is also your single best activation lever — it's what gets a new user to a working agent in 5 minutes. So **don't paywall whether the AI can build; paywall how much, how powerful, and how deep:**

| | Free | Paid |
|---|---|---|
| AI generation | Yes — cheaper model, capped runs/tokens, single-to-moderate complexity | Frontier model, higher limits |
| Iterative copilot | — | Watches runs, debugs, explains, self-heals, extends an existing graph |
| Multi-agent complexity | Limited | Full |
| Team / collaboration (co-edit, versioning, review) | — | Yes — the NRR / seat-expansion engine |
| Share runnable prototype to test | **Yes — generous** (the viral growth loop; don't paywall the front door) | Yes |

The thing people pay for isn't "AI writes a workflow once" — that's a demo. It's the **iterative copilot that understands their existing agent and helps extend and fix it.** One-shot generation is the hook; conversational refinement on a live graph is the product.

**Quality is the trap — and your opening.** A user building a multi-agent system *because they don't know how* cannot evaluate whether the AI built it correctly. This is exactly where one-shot generators demo well and break in production. Your other layers are the answer: AI generates → the **code layer shows exactly what it built** (readable, yours) → **eval hooks validate it before it ships.** "AI builds your agent, and you can see and own every line" is a sentence no competitor can say.

**Two hard constraints.** (1) *Margin* — AI generation is the most token-hungry feature you can ship; meter and cap it per tier, route free-tier generation to a cheap model, never let an unbounded "build me a system" prompt run uncapped. (2) *Don't cannibalize the canvas* — keep the altitudes distinct: AI proposes, human reviews on the canvas, code is the receipt. The AI must not become a black box that eats the trust layer.

## 3. The one bet that must be true

Everything rides on **round-trip code quality**. If the generated code is "messy but works," the entire premise collapses — because the promise is *trustable, ownable* code. Before scaling spend, we must prove two things:

1. **Code quality** — an engineer would accept the generated code in a PR without rewriting it.
2. **No-ceiling retention** — users who hit complexity drop into code and *stay*, instead of churning.

The 90 days exist to validate these two — cheaply, before betting the company.

---

## 4. The 90-day plan

### Phase 1 — Prove the artifact (Days 0–30)
**Goal:** Round-trip works and the code is good enough that an engineer trusts it.

- Lock the visual ⇄ code round-trip for the core node set (tools, RAG, multi-agent handoff). Edits in code must survive a return to canvas, and vice versa.
- Run a **blind code-quality panel:** 5–8 senior engineers review generated code with no context. Score readability, idiomatic structure, and "would you merge this?" Target ≥ 4/5 mean and ≥ 70% "would merge."
- Recruit 15–25 design partners from the ICP (lean agencies + technical founders). Hand-onboard. Watch them build one real agent each.
- Instrument from day one (see §4) — cost metering, eval hooks, and code-drop events especially.

**Exit gate:** ≥ 70% "would-merge" on the blind panel **AND** ≥ 10 design partners with a real agent running. If code quality misses, *stop and fix it* — no growth spend until this passes.

### Phase 2 — Prove no-ceiling retention (Days 30–60)
**Goal:** Show that hitting complexity drives users *into* code, not *out* the door.

- Open a waitlisted beta to the ICP. Keep it narrow enough to support well.
- Ship 6–8 templates that intentionally span the simple→complex gradient (single-tool → RAG → multi-agent), so users naturally reach the wall and discover the code drop-down.
- Track the **ceiling event:** when an agent exceeds what the canvas comfortably expresses, do they (a) drop into code and continue, or (b) churn? This ratio is the whole thesis.
- Weekly design-partner interviews: where did they hit the wall, did code save them, would they have left otherwise.

**Exit gate:** ≥ 50% of users who hit a ceiling event drop into code and keep the agent live 14+ days afterward. 30-day agent retention ≥ 40% for the cohort.

### Phase 3 — Prove willingness to pay & concentrate (Days 60–90)
**Goal:** Confirm the segment pays, and let the data pick the sub-segment to dominate.

- Turn on paid tiers (hybrid seat + usage). Charge real money — willingness to pay is the only honest signal.
- Segment retention & conversion by ICP sub-type (agencies vs. product teams vs. solo technical founders). One will over-index.
- Stand up the agency/MSP motion as a channel test: can one agency deploy Calypr agents to ≥ 3 of their clients?
- Decide the concentration: messaging, templates, and onboarding now speak to the winning sub-segment — runtime stays open underneath.

**Exit gate (go-to-G1):** ≥ 25 paying workspaces, ≥ 40% 30-day agent retention, **positive gross margin per run**, and ≥ 1 segment converting ~3× the others.

---

## 5. Metrics to track

**North star:** weekly active agents in production (deployed *and* used by end users).

### The wedge-specific metrics (these are unique to your bet — watch them hardest)
| Metric | What it tells you | Target by Day 90 |
|---|---|---|
| **Code-drop rate** | % of active agents that have been edited in code at least once | ≥ 30% |
| **Round-trip survival** | % of code-edited agents successfully returned to canvas without breakage | ≥ 95% |
| **Ceiling-event resolution** | At a complexity wall, % who drop into code & continue vs. churn | ≥ 50% continue |
| **Blind code-quality score** | Engineer panel "would you merge this?" | ≥ 70% yes |
| **Post-code retention** | % still live 14 days after first code edit | ≥ 60% |

### AI copilot layer (validate before charging for it)
| Metric | What it tells you | Target by Day 90 |
|---|---|---|
| **AI-built vs. hand-built retention** | Do AI-generated agents survive 30 days as well as hand-built ones? | AI ≥ hand-built |
| **Copilot-attributed upgrades** | % of free→paid conversions driven by hitting the AI cap or wanting the iterative copilot | ≥ 30% of conversions |
| **Generation acceptance rate** | % of AI-built workflows the user keeps without major rework | ≥ 60% |
| **Cost per generation** | Token spend per AI build (watch the tail on complex multi-agent prompts) | Capped per tier; positive margin |

> Kill-signal: if complex AI-built agents churn *faster* than simple hand-built ones, the copilot is producing impressive garbage — fix quality before charging.

### Collaboration & virality (the Figma loop)
| Metric | What it tells you | Target by Day 90 |
|---|---|---|
| **Prototype-share → signup** | Viral coefficient — recipients of a shared prototype who sign up | track; aim ≥ 0.3 |
| **Seats per paying workspace** | Whether collaboration drives seat expansion (NRR) | growing month over month |
| **Async vs. real-time demand** | Do engineers want versioning/branches/review, or live co-editing? | validate *before* building heavy real-time |

> Test cheaply: ship versioning + share-to-test first. Only build live multiplayer if engineers actually ask for it — async (GitHub-style) may be enough and is far cheaper.

### Activation
- Time to first agent run: **< 5 min**
- Time to first deployed agent: **< 1 day**
- % of signups reaching first run (activation rate): **≥ 40%**

### Retention (the real verdict)
- **30-day agent retention** (agent still turned on): **≥ 40%** — this is the single number that decides whether you have a product
- Workspace 30-day retention
- Agents per workspace, runs per agent

### Revenue & unit economics
- Paying workspaces: **≥ 25** by Day 90
- **Gross margin per run** (LLM cost vs. price) — track relentlessly; gate everything on it staying positive
- ARPU; early NRR signal; conversion rate free → paid by segment

### Quality & reliability (your edge — instrument as proof)
- Eval pass rate per template/graph version
- p95 run latency; cost per run
- Agent error / silent-failure rate (your differentiator is reliability — measure it)

### Leading kill-signals (watch weekly)
- Code-drop rate near zero → the wedge isn't real; users don't value the code
- High ceiling-event *churn* → the canvas-to-code handoff is too painful
- Flat 30-day retention across *all* segments → it's a product-quality problem, not a market problem; no positioning fixes it

---

## 6. Go / no-go gates (decision rules, not vibes)

- **End of Phase 1:** Code quality < 70% would-merge → halt growth, fix code generation. The bet is dead without this.
- **End of Phase 2:** Ceiling-event resolution < 50% → the "no-ceiling" claim is false; either the round-trip UX is broken or the segment doesn't actually want code. Diagnose before spending.
- **End of Phase 3:** < 25 paying workspaces OR negative gross margin OR no segment separation → don't scale; iterate on the wedge or revisit ICP. If retention is flat *everywhere*, the problem is the core product loop, not the market.
- **Green across all three:** concentrate on the winning sub-segment and execute your existing G1.

---

## 7. Risks specific to this wedge

- **Generated-code quality is the hardest engineering bet in the plan and it's binary.** "Good enough" isn't good enough. Resource it like the core product, because it is.
- **Bidirectional round-trip is genuinely hard** — it's why most tools only export. That difficulty is also the moat. Don't ship export-only and call it the wedge.
- **Cannibalization:** if code-ownership reads as "leave us," you train churn. Anchor pricing and value on the *running* product and collaboration, not on possession of the code.
- **ICP coherence:** this wedge points at technical builders. Don't simultaneously market to non-technical merchants — the messaging cancels out. Open runtime, focused voice.
- **AI-layer margin & trust:** the copilot is your most token-hungry feature and your biggest trust risk at once. Cap and meter it from day one, route free generation to a cheap model, and make code-inspectability the answer to "I can't tell if the AI built this right."
- **Demand is still the assumption.** These 90 days exist to falsify it cheaply. Let the data kill bad bets fast.

---

## The one next action

Before anything else: run the **blind code-quality panel** in week 1. It's cheap, it's fast, and it tells you whether you have a company or a demo. If senior engineers won't merge the code, nothing downstream matters — and you'll have learned it for the price of a few coffees instead of a year.
