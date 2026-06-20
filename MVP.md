# Calypr — Post-MVP Growth Plan

> **⤳ Superseded (2026-06-20) by [`WEDGE-PLAN.md`](./WEDGE-PLAN.md).** Calypr's ICP is now
> the **AI engineer**, and the live growth/validation plan is the **No-Ceiling Wedge**
> (prompt → canvas → code, round-trip). The **E-Commerce vertical-first strategy below is
> deferred** to a possible post-validation vertical — kept for reference, not the current
> direction. The retained, still-valid parts are the cross-cutting production-readiness and
> ecosystem workstreams (Workstreams A, C, D), which are ICP-agnostic.

**Boundary:** MVP = Phases 0–3 (canvas → compiler → RAG → multi-agent templates). Phases 4–6 (tools, marketplace v0, initial hardening) are the bridge. **This plan is what you double down on once real users are running agents.**

**Strategy in one line:** Win E-Commerce deeply with native connectors and opinionated templates, let the ecosystem (SDK + marketplace) fill the long tail, and convert self-serve users on usage and premium templates.

| | |
|---|---|
| **Status** | DRAFT — execute once MVP is live with real users |
| **Last updated** | 2026-06-19 |
| **Companion doc** | `PLAN.md` — foundation build plan |

## Confirmed strategy

- **Expansion strategy:** Vertical-first (go deep in E-Commerce, then Sales/RevOps).
- **Ecosystem:** Open early (connector SDK + template marketplace).
- **GTM motion:** Product-led growth (self-serve; enterprise layered on later).

## How the three choices interlock

E-Commerce templates are the **PLG magnets**, the **marketplace** lets the ecosystem fill the long tail, and **vertical depth** wins the wedge. They reinforce each other rather than compete for resources.

---

## Workstream A — Production readiness

| Area | What "done" looks like |
|------|------------------------|
| Reliability / SLOs | 99.9% target + error budgets; multi-LLM provider failover (OpenAI ↔ Anthropic ↔ Google); circuit breakers; retries + backoff; idempotency; per-tenant rate limits. |
| Scalability | Autoscaling runtime workers; managed Postgres (HA + replicas + PITR); Redis HA; queue backpressure; HNSW vector tuning; per-tenant partitioning strategy; PgBouncer pooling. |
| **Cost & margin control** | Smart model routing, prompt/result caching, per-agent/run/tenant token budgets + hard caps, cost dashboards, margin alerts. **The #1 business risk — protect unit economics from day one.** |
| Security & compliance | SOC 2 Type I → II; GDPR/CCPA + DPAs; encryption at rest/in transit; secrets via KMS/Vault; **automated RLS isolation tests**; pen tests; SBOM; incident runbooks. |
| Observability | OpenTelemetry end-to-end; per-run debug traces in the UI; LangFuse/LangSmith tied to cost + quality; metrics, dashboards, alerting. |
| Quality / evals | In-product eval suites; regression tests on every template/graph change; publish quality gates; A/B test agent versions; drift monitoring. |
| Data lifecycle | Tested restores; retention policies; tenant data export + deletion (GDPR); vector re-indexing/migrations. |
| DevEx / Deploy | CI/CD with canary/feature flags; expand-contract migrations; staging/prod parity; on-call runbooks. |

## Workstream B — Vertical-first expansion

### Vertical 1: E-Commerce (the wedge — go deep)

- **Native connectors:** Shopify, WooCommerce, Klaviyo, Gorgias/Reamaze, Google Merchant Center/Shopping, Meta Ads, Google Ads, ShipStation. Both knowledge sources and action tools.
- **Templates beyond the MVP three:** Reviews responder, Abandoned-cart recovery, Catalog enrichment/PIM, Ad copy + audience, Order/returns automation, Inventory alerts, Competitor monitoring.
- **Vertical features:** product-catalog node, scheduled store sync, image-gen node (ad/product creative), brand-voice consistency across agents, merchandising approval queues.

### Vertical 2: Sales/RevOps *(next — gated on E-Commerce traction)*

- **Connectors:** HubSpot, Salesforce, Pipedrive, Gmail, Google Calendar, Slack, Zoom.
- **Templates:** lead qualification, meeting prep, follow-up sequences, CRM hygiene, proposal drafts, outbound research, inbound triage.
- **Same playbook:** PLG magnets → dominate → ecosystem fills the tail.

> **Open item (to confirm):** Vertical 2 = Sales/RevOps is the recommended default. Alternatives: Support/Helpdesk, or Marketing. Decide before G3.

### Cross-vertical capabilities (unlock all templates)

Code-interpreter node (sandboxed), HTTP/API node, DB query node, branching/loops/parallel, memory types (episodic/semantic), **MCP client support** (any MCP server becomes tools), embeddable chat widget, per-agent REST API, Slack/Teams bots, email-in agents, scheduled/webhook/event triggers, team workspaces + versioning + approvals, analytics dashboard, learning-from-edits memory.

## Workstream C — Open ecosystem (the growth multiplier)

- **Connector SDK** (TS + Python): build/publish a connector with validation, local test harness, and sandboxed execution for untrusted code.
- **Template marketplace:** publish/install/review/version, categories, verified-creator program, revenue share, curated + enterprise packs.
- **Public API + SDKs:** build and deploy agents programmatically — turns agencies/MSPs into a channel.
- **MCP support (both directions):** Calypr as MCP client (use any MCP server as nodes) and MCP server (Calypr agents exposed as tools).
- **Creator program:** docs, example templates, office hours, partner tiers, revenue share.
- **Marketplace trust:** automated checks + human review before publish, sandboxing, ratings, abuse reporting, security review for elevated-scope connectors.

## Workstream D — PLG revenue engine

- **Pricing tiers:** Free (limited runs/tokens, community templates) → Team (seat + usage, collaboration) → Business (higher limits, SLAs) → **Enterprise (SSO/SAML, SOC 2 report, data residency, dedicated infra) added as pipeline warrants.** Hybrid seat + usage.
- **Usage monetization:** per-run, per-token, per-embedding, premium models, premium/marketplace templates (revenue share).
- **Growth loops:** public SEO-indexed template pages → signups; "first value in 5 min" onboarding; usage-based upgrade prompts; referrals; "powered by Calypr" on embeds; case studies from vertical wins.
- **Funnel instrumentation:** signup → first run → first publish → paid; self-serve billing; usage + cost dashboards so users self-manage.

## Growth phases (quarters, post-MVP)

| Phase | Focus | Exit criterion |
|-------|-------|----------------|
| **G1** | Productionize + E-Commerce depth + PLG foundations: SOC 2 Type I, provider failover + cost controls, in-product evals, deep E-Commerce connectors, 6–8 templates, paid tiers + funnel analytics | E-Commerce users converting to paid; **positive gross margin per run** |
| **G2** | Open ecosystem v1 + marketplace: connector SDK, public API, template marketplace (reviews + revenue share), MCP client, collaboration (team/versioning), richer nodes | First third-party template published + installed |
| **G3** | Vertical 2 (Sales/RevOps) + scale: Sales templates + CRM/Gmail/Calendar connectors, SOC 2 Type II, multi-region/HADR, analytics dashboard, Enterprise tier (SSO/SAML), creator program | Second revenue vertical live; enterprise deals closing |
| **G4** | Moat + expand: MCP server, voice/email-in agents, A/B testing + drift monitoring, i18n + EU region, partner/channel program, marketplace network effects | Ecosystem compounding growth; defensible position |

## Metrics & north star

- **North star:** weekly active agents in production (deployed + used by end users).
- **Activation:** first agent run < 5 min; first publish < 1 day.
- **Revenue:** MRR, NRR (expansion via usage + seats), ARPU, **gross margin** (LLM cost vs revenue — track relentlessly), CAC, LTV/CAC.
- **Product:** agents per workspace, runs per agent, template install → publish rate.
- **Ecosystem:** community templates/connectors, % installs from community, creator count, marketplace GMV + take rate.
- **Quality:** eval pass rates, incident rate, CSAT/NPS.
- **Reliability:** uptime vs SLO, error-budget burn, p95 run latency, cost per run.

## Risks & open questions

- **LLM margin compression** — model cost vs price charged. The single biggest business risk. Smart routing + premium tiers + rigorous margin monitoring. Gate everything on gross margin.
- **Vertical-fit risk** — vertical-first under-invests if E-Commerce doesn't convert. Set an explicit go/no-go gate on Vertical 2 based on E-Commerce traction.
- **Marketplace quality/safety** — third-party code can be insecure or bad. Sandbox + review + ratings before it becomes a liability. **Don't launch the marketplace before real PLG traction (G2, not earlier).**
- **Compliance timing** — PLG-first lets SOC 2 wait slightly, but enterprise pipeline needs it. Start Type I in G1 so it never blocks.
- **Platform deps** — LangGraph/LangChain + provider churn. Keep the compiler behind an interface; minimize LangChain surface.
- **Demand is the assumption** — this whole plan presumes the MVP finds users. Keep validating during MVP; don't scale something nobody wants.

## Vertical 2 go/no-go gate (proposed — to confirm)

> **Open item:** concrete trigger metrics for launching Vertical 2. Proposed default:
> - NRR **≥ 110%**, AND
> - **≥ 25 paying E-Commerce workspaces**, AND
> - gross margin per run **≥ 60%**.
>
> If E-Commerce misses these by end of G2, hold Vertical 2 and double down on the wedge instead. Confirm/adjust these thresholds.

## The one next action (do during MVP to make this plan executable)

**Build the expandability primitives into the MVP now**, so post-MVP growth is additive, not a rewrite:

1. Clean **node-type registry** + **connector abstraction** (so new nodes/connectors are plugins).
2. **Versioned DSL** with codegen (already planned) — keep it forward-compatible.
3. **Eval hooks** + **per-tenant cost metering** wired in from Phase 0.

Then the first post-MVP move (G1) is concrete: ship SOC 2 Type I, provider failover + cost controls, the first 6–8 deep E-Commerce templates with native connectors, and turn on paid tiers + funnel analytics.
