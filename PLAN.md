# Calypr — Build Plan (Foundation)

**What it is:** A standalone, multi-tenant SaaS where users design AI agents on a visual canvas. The canvas compiles to **LangGraph** and runs in our hosted runtime. A **template gallery** jumpstarts users: **RAG templates** (Customer Service, Document Q&A, single-agent) and **E-Commerce templates** (Copywriting, Support, SEO, multi-agent teams).

**Stack:** Next.js + React Flow (canvas) · Python/FastAPI · LangGraph (runtime + Postgres checkpointer) · Celery/Arq (platform jobs) · Postgres+pgvector (RLS on `tenant_id`) · Redis · Clerk (auth) · Stripe (billing) · OpenAI/Anthropic/Google · Vercel + containers.

| | |
|---|---|
| **Status** | DRAFT — ready to build |
| **Last updated** | 2026-06-19 |
| **Companion doc** | `MVP.md` — post-MVP growth plan |

## Confirmed decisions

- Canvas: **custom (React Flow / xyflow)** + proprietary graph DSL that compiles to LangGraph.
- Product: **no-code canvas builder** + template gallery (not fixed presets).
- Hosting: **standalone multi-tenant SaaS**; we host and run agents.
- Topologies: **single-agent + multi-agent** both supported in MVP.
- Runtime durability: **LangGraph Postgres checkpointer** (native to LangGraph).
- Catalog data for E-Commerce templates: **treated as a knowledge base** for MVP (native Shopify/GMC integration deferred to post-MVP).
- First de-risk milestone: compile a canvas graph of `Input → LLM → Output` into a LangGraph graph that runs in the playground.

---

## 1. Architecture overview

```
┌─────────────────────────────────────────────┐
│  Next.js (Vercel)                            │
│   Canvas (React Flow) · Template gallery     │
│   Dashboard · Playground · Billing           │
└──────────────────┬──────────────────────────┘
                   │  graph DSL (TS, codegen-shared)
┌──────────────────▼──────────────────────────┐
│  FastAPI API                                 │
│   auth · CRUD · compile · run · knowledge    │
└──────┬────────────┬──────────────┬──────────┘
       │            │              │
       ▼            ▼              ▼
┌────────────┐ ┌─────────────┐ ┌──────────────┐
│ Compiler   │ │ Runtime     │ │ Ingestion    │
│ DSL →      │ │ LangGraph + │ │ docs/url →   │
│ StateGraph │ │ Postgres    │ │ embed →      │
│ (the IP)   │ │ checkpointer│ │ pgvector     │
└─────┬──────┘ │ streaming,  │ └──────────────┘
      │        │ HITL resume  │
      │        └──────┬───────┘
      │               │ invoke
      │        ┌──────▼───────┐
      └───────▶│ LLM gateway  │ OA/Anthropic/Google,
               │              │ BYOK + metering
               └──────────────┘
        ┌──────────────────────────────┐
        │ Postgres + pgvector          │
        │ RLS: every row tenant_id     │
        │ AgentVersions, Runs, KB,     │
        │ Usage → Stripe meter         │
        └──────────────────────────────┘
        Celery/Arq + Redis: schedules, webhooks, batch embeddings
```

## 2. Stack decisions

| Layer | Choice | Reason |
|-------|--------|--------|
| Canvas | **React Flow (xyflow) + custom** | UX is the product in no-code tools. Own it. |
| Agent framework | **LangGraph** | State graphs, conditional routing, subgraphs (multi-agent), native interrupts (HITL), Postgres checkpointer for durable state. |
| Runtime durability | **LangGraph Postgres checkpointer** | Native to LangGraph; handles state + HITL interrupts + streaming. Avoids reinventing durable execution for agent runs. |
| Platform jobs | **Celery or Arq + Redis** (Temporal if it grows) | Scheduled runs, webhooks, batch embeddings. Lighter than Temporal for this scope. |
| DSL | **Pydantic → generated TS** | One graph schema, shared by canvas (TS) and compiler (Python). This contract is the most important rule in the system. |
| UI | **Next.js + shadcn/ui + Tailwind** | Polished SaaS UX fast. |
| Data | **Postgres + pgvector, RLS on `tenant_id`** | Relational + vector in one, per-tenant isolation at the DB. |
| Auth / Billing | **Clerk (org=tenant) + Stripe** | Standard multi-tenant SaaS. Stripe Meter for usage. |
| Tracing/Evals | **LangSmith or LangFuse** | Agent quality is 90% eval discipline. Wire in at Phase 2. |
| Deploy | **Vercel + Fly/Render containers** | Web on Vercel; api/runtime/workers in containers (never serverless for runs). |

## 3. The three hard parts (where the real engineering is)

### 3.1 The canvas node system (React Flow)

Node types: `Input`, `Prompt`, `LLM`, `RAG Retriever`, `Tool`, `Router` (conditional), `Sub-agent`, `Human Input`, `Output`, `Memory`.

- Each node has a typed config panel.
- Edges carry typed data.
- A **State editor** defines the variables/types that flow through the graph (LangGraph state channels), because every node reads/writes state.

### 3.2 The DSL → LangGraph compiler (the IP)

Canvas emits a JSON graph spec. The compiler turns it into a LangGraph `StateGraph`:

- Node types → LangGraph node callables.
- Edges → transitions; `Router` nodes → conditional edges / routing functions.
- State schema (from the State editor) → typed state with channels.
- `RAG Retriever` → retriever bound to a chosen knowledge base.
- `Tool` → tool executor (from the tool registry).
- `Sub-agent` → compiled subgraph (multi-agent supervisor/hierarchical pattern).
- `Human Input` → `interrupt()`; resume via API.
- Checkpointer → Postgres saver, keyed by thread/run id.
- **Validation:** type-check the graph (no dangling inputs, compatible types, intentional cycles).

Every published graph is **immutable + versioned**; runs reference `(agent_id, version)`.

### 3.3 Multi-agent (supervisor) topology

E-Commerce templates are teams: a supervisor routes to workers (Copywriter, Support, SEO). The compiler maps `Sub-agent` nodes to LangGraph subgraphs and a supervisor graph orchestrates them. Lands in Phase 3; the heaviest phase.

## 4. RAG layer (shared by all RAG + E-Commerce templates)

- **Sources:** document upload, URL/website crawl, paste text. (Later: Notion, Google Drive, Shopify/GMC catalog feed.)
- **Pipeline:** chunk → embed → pgvector, scoped per tenant + per knowledge base.
- **Retrieval:** hybrid (vector + metadata filters), with citations surfaced in the playground.
- A knowledge base is a first-class object an agent's `RAG Retriever` node binds to.

## 5. Templates (MVP set)

| Category | Template | Topology |
|----------|----------|----------|
| RAG | Customer Service (policies/FAQs + escalate tool) | single-agent |
| RAG | Document Q&A (upload + cited answers) | single-agent |
| E-Commerce | Support team (supervisor + triage + responder + RAG) | multi-agent |
| E-Commerce | Copywriting team (supervisor + product/ad/editor) | multi-agent |
| E-Commerce | SEO team (supervisor + research/write/optimize) | multi-agent |

E-Commerce templates need a product catalog source. For MVP, treat the catalog as a knowledge base (upload/feed); native integrations later.

## 6. Core data model (tenant-keyed)

```
Workspace (tenant) ─┬─ User, Membership, Role
                    ├─ Agent (canvas spec) ─┬─ AgentVersion (immutable, compiled graph ref)
                    │                        ├─ AgentRun (thread id, status, checkpointer refs)
                    │                        └─ RunTrace (steps, tokens, latency)
                    ├─ KnowledgeBase ─┬─ Source (upload/url/paste/integration)
                    │                  └─ Document → Chunk → Embedding (pgvector)
                    ├─ Tool (registry + credentials)
                    ├─ Template (category: rag|ecommerce, spec, params)
                    ├─ TemplateInstall (agent ← template)
                    ├─ ApiKey (per agent / workspace)
                    ├─ UsageEvent (tokens, runs, embeddings → Stripe meter)
                    └─ AuditLog
```

`tenant_id` on every row + Postgres RLS. No query crosses workspaces.

## 7. Repo structure

```
calypr/
  apps/
    web/            # Next.js: canvas, template gallery, dashboard, playground, billing
    api/            # FastAPI: auth, CRUD, compile, run, knowledge, billing
  services/
    compiler/       # DSL (Pydantic) → LangGraph StateGraph  ← the IP
    runtime/        # LangGraph execution, Postgres checkpointer, streaming, HITL resume
    ingestion/      # docs/url/crawl → chunk → embed → pgvector
    jobs/           # Celery/Arq: schedules, webhooks, batch embeddings
    llm-gateway/    # provider abstraction, BYOK, per-tenant metering
  packages/
    dsl/            # shared graph spec (Pydantic → TS) — single source of truth
    nodes/          # node type metadata + config schema (shared web+api)
    ui/             # shadcn component lib + canvas node components
  infra/
    docker/ alembic/ checkpoint-db/ seed/
```

The `dsl` package being shared (Pydantic → TS codegen) is the load-bearing contract. Canvas and compiler must never drift.

## 8. Phased roadmap

| Phase | Deliverable | Exit criterion |
|-------|-------------|----------------|
| **0. Foundation** | Monorepo; Next.js + FastAPI; Clerk (org=tenant); Postgres+pgvector+RLS; Stripe skeleton; health/logging/OTel; CI | User signs in, lands on dashboard |
| **1. Canvas + compiler MVP (single-agent)** | React Flow canvas with `Input`, `Prompt`, `LLM`, `RAG Retriever`, `Output`; the DSL; DSL→LangGraph compiler; runtime with Postgres checkpointer; in-app playground; knowledge ingestion (upload + URL) | Draw a RAG agent on canvas → chat with it in playground |
| **2. RAG templates + evals** | Template gallery + install-to-canvas; ship Customer Service RAG + Document Q&A; citations; LangSmith/LangFuse tracing + golden evals | Non-expert installs a template, customizes, ships a working agent |
| **3. Multi-agent + E-Commerce templates** | `Sub-agent` node, supervisor topology in compiler, `Router`/handoffs; ship Support (multi-agent), then Copywriting + SEO | A multi-agent team runs end-to-end from canvas |
| **4. Tools, triggers, deploy** | Tool registry (web search, HTTP, code-interpreter*); per-agent REST API + API keys; chat-widget embed; scheduled/webhook triggers; BYOK + managed-key metering | External traffic hits a user's published agent |
| **5. Marketplace + monetization** | Template marketplace (publish/install/review); Stripe usage billing via Meter; vertical template packs | Third-party template published; usage billed |
| **6. Scale & hardening** | Per-tenant isolation review; cost controls; eval harness; observability; SOC2-track; perf | Production-grade |

Phase 0–1 is the MVP proof (canvas → run). Phase 2–3 is the product. Phase 4–6 is the business.

> **\*Code interpreter is security-critical:** sandboxed (gVisor/Firecracker) or deferred.

## 9. Cross-cutting (from Phase 0)

- **DSL is the contract** — version it, validate it, share types via codegen. Most important architectural rule.
- **Minimize LangChain exposure** — prefer LangGraph primitives + direct provider SDKs; wrap the compiler behind our interface. LangChain churn is real.
- **Evals from Phase 2** — every template ships with golden test cases; regression-test compiled graphs on every change.
- **Per-tenant cost metering** → Stripe Meter. LLM cost is the margin killer.
- **HITL** via LangGraph interrupts (native, clean).
- **Security** — RLS, envelope-encrypted credentials, API-key vault, sandboxed code execution.

## 10. Risks & open questions

- **The compiler is genuinely hard.** Type system, graph validation, conditional routing, subgraph composition. Budget real time. The Phase 1 thin slice exists to de-risk exactly this.
- **Crowded space** (Langflow, Flowise, Relevance, Lindy). Differentiation = superior no-code UX + opinionated templates + hosted multi-agent. Get a Phase-2 prototype in front of real users fast.
- **Multi-agent complexity** (Phase 3) — supervisor routing, subgraph state. Don't underestimate.
- **E-Commerce catalog data** — MVP treats it as a knowledge base; native Shopify/GMC integration later.
- **LangGraph/LangChain churn** — mitigated as above.
- **Demand is the assumption** — this plan presumes the MVP finds users. Keep validating during the build; put a clickable prototype in front of users by end of Phase 2.

## 11. The one next action

**Phase 0 + a compiler spike as the first milestone.** Scaffold the monorepo, then build the thinnest end-to-end slice before anything else: a canvas with `Input → LLM → Output` whose DSL compiles to a LangGraph graph that runs in the playground. This de-risks the single hardest piece (the compiler) immediately. If that slice works, everything else is execution.
