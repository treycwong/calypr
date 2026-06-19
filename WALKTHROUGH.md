# Calypr — Walkthrough (Phases 0 & 1)

> **Who this is for:** an AI engineer who's newer to building a real product. By the end
> you'll understand *what* Calypr is, *how* the codebase is laid out, and *why* each piece
> exists. We build in small, verified steps — every phase ends with a test that must pass
> before we move on.
>
> **Companion docs:** [`CLAUDE-PLAN.md`](./CLAUDE-PLAN.md) (architecture + full roadmap),
> [`PLAN.md`](./PLAN.md), [`MVP.md`](./MVP.md).

---

## 1. The 30-second mental model

Calypr lets people **build AI agents by drawing them on a canvas** instead of writing code.
You drag blocks (an *Input*, an *Agent*, an *Output*) onto a canvas, connect them, and Calypr
turns that drawing into a running program.

The key idea that makes this tractable:

> **An agent is a *typed state graph*.** There's a shared bag of data (the **state**),
> **nodes** that read and write that data, and **edges** that decide what runs next.

We use **[LangGraph](https://langchain-ai.github.io/langgraph/)** (a Python library) as the
engine that actually executes these graphs. Our job is to (a) let users *describe* a graph
visually, and (b) *compile* that description into a LangGraph graph and run it.

```
   A user's drawing                Our job                    What runs
 ┌───────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
 │ Input → Agent →   │ →  │ DSL (a JSON spec)    │ →  │ LangGraph StateGraph │
 │        Output     │    │ → Compiler           │    │ → streams a reply    │
 └───────────────────┘    └──────────────────────┘    └──────────────────────┘
   (Phase 2 builds this)    (Phase 1 — done)             (Phase 1 — done)
```

Phases 0 and 1 (this document) build the **foundation** and the **engine**. The visual canvas
itself comes in Phase 2 — but the engine it will drive already works today.

---

## 2. The tech stack (and why)

Calypr is a **polyglot monorepo**: one git repository holding both TypeScript and Python
projects that work together.

| Layer | Tool | Why |
|---|---|---|
| Canvas / web UI | **Next.js 16 + React 19 + Tailwind + shadcn/ui** | The UX *is* the product for a no-code tool. |
| Visual graph | **React Flow (xyflow)** | Battle-tested node/edge canvas. |
| Agent engine | **LangGraph (Python)** | State graphs, durable state, the natural fit for agents. |
| API | **FastAPI (Python)** | Fast, typed, async Python web framework. |
| Database | **Postgres + pgvector** | Relational data *and* vector search (for RAG later) in one DB. |
| LLM providers | **OpenAI + Anthropic** behind a thin interface | Swap providers without touching the engine. |
| JS package manager | **pnpm** (workspaces) | Fast, disk-efficient monorepo support. |
| Python package manager | **uv** (workspaces) | Extremely fast; manages venvs + multiple packages. |
| Tests | **pytest** (Python) + **Playwright** (browser E2E) | Unit/integration + real-browser checks. |

**Monorepo jargon:** a *workspace* is a set of sub-projects (here called *packages*) that live
in one repo and can depend on each other directly. pnpm manages the TypeScript packages; uv
manages the Python ones. They coexist at the repo root.

---

## 3. Repo map

```
calypr/
├── apps/
│   ├── api/          # FastAPI service        (Python pkg: calypr-api)
│   └── web/          # Next.js app            (JS pkg: @calypr/web)
├── packages/
│   ├── dsl/          # GraphSpec contract     (calypr-dsl + @calypr/dsl)  ← the contract
│   └── nodes/        # node registry + types  (calypr-nodes)              ← the plugin backbone
├── services/
│   ├── model/        # ModelClient + adapters (calypr-model)              ← the LLM seam
│   ├── compiler/     # GraphSpec → StateGraph (calypr-compiler)           ← the IP
│   └── runtime/      # run + stream + memory  (calypr-runtime)
├── e2e/              # Playwright browser tests (@calypr/e2e)
├── infra/docker/     # Postgres (pgvector) via docker compose
├── .github/workflows # CI pipeline
├── pyproject.toml    # uv workspace + ruff + pytest config
├── pnpm-workspace.yaml
└── CLAUDE-PLAN.md    # architecture + roadmap
```

A good way to read the code: **bottom-up** — `packages/dsl` → `services/model` →
`packages/nodes` → `services/compiler` → `services/runtime`. That's also the dependency order.

---

## 4. Phase 0 — The Foundation

**Goal:** a real, deployable skeleton — a user can sign in and land on a dashboard, the
database is up, and CI is green. *No agent logic yet.* The point is to get all the plumbing
right before building features on top.

### 4.1 The monorepo skeleton

Two workspaces are declared at the root:

- `pnpm-workspace.yaml` lists the JS packages (`apps/*`, `packages/*`, `e2e`).
- [`pyproject.toml`](./pyproject.toml) declares the uv workspace members (the Python packages)
  plus shared config for **ruff** (linter/formatter) and **pytest**.

Each Python package has its own tiny `pyproject.toml`; uv links them so `calypr-api` can
`import calypr_dsl` directly. One shared virtual environment (`.venv`) holds everything.

### 4.2 The API (`apps/api`)

A minimal **FastAPI** service. The important files:

- [`main.py`](apps/api/src/calypr_api/main.py) — creates the app and exposes `/health`
  (liveness: "the process is up") and `/readyz` (readiness: pings the DB, returns 503 if down).
- [`config.py`](apps/api/src/calypr_api/config.py) — settings via **pydantic-settings**. Every
  setting is read from an env var prefixed `CALYPR_` with a sensible local default, so the app
  runs with zero configuration locally.

> **Lesson:** separate *liveness* from *readiness*. Liveness = "am I running?"; readiness =
> "can I serve traffic (are my dependencies up)?". Load balancers use these differently.

### 4.3 The database (`apps/api/.../db` + `infra/docker`)

- [`infra/docker/compose.yaml`](infra/docker/compose.yaml) runs **Postgres with the pgvector
  extension** (we'll need vector search for RAG in Phase 3) in a container.
- **[Alembic](https://alembic.sqlalchemy.org/)** manages database *migrations* (versioned,
  repeatable schema changes). The baseline migration
  [`0001_baseline.py`](apps/api/migrations/versions/0001_baseline.py) does three things:
  1. enables the `vector` extension,
  2. creates a `workspace` table (a *tenant* — one customer/organization), and
  3. turns on **Row-Level Security (RLS)** with a policy.

> **Multi-tenancy + RLS, explained:** Calypr is multi-tenant — many customers share one
> database. RLS is a Postgres feature where the database *itself* filters every query to the
> current tenant, so customer A can never see customer B's rows — even if app code has a bug.
> We set the current tenant per request via a session variable (see `set_tenant()` in
> [`session.py`](apps/api/src/calypr_api/db/session.py)). Every future table follows this same
> pattern.

### 4.4 The DSL contract (`packages/dsl`) — *the most important idea in Phase 0*

The canvas is TypeScript; the engine is Python. They must agree **exactly** on the shape of a
graph, or the whole thing breaks. So we make **one source of truth** and generate the other side:

```
Pydantic models (Python)  →  JSON Schema  →  TypeScript types
   (the source of truth)       (codegen)        (used by the canvas)
```

- [`spec.py`](packages/dsl/src/calypr_dsl/spec.py) defines the **`GraphSpec`** (and
  `StateChannel`, `NodeSpec`, `EdgeSpec`) as **Pydantic** models. Pydantic is a Python library
  for typed, validated data models.
- [`codegen.py`](packages/dsl/src/calypr_dsl/codegen.py) dumps those models to a JSON Schema;
  [`gen-ts.mjs`](packages/dsl/scripts/gen-ts.mjs) turns that schema into TypeScript types.
- A **drift check** (`pnpm --filter @calypr/dsl gen:check`) re-runs the generation and fails CI
  if the committed TypeScript is out of date. This guarantees the two languages never disagree.

> **Lesson:** when two systems must share a data shape, don't hand-write it twice. Pick one
> source of truth and *generate* the rest, then enforce it in CI. This is the single
> load-bearing rule of the project.

### 4.5 The web shell (`apps/web`)

A **Next.js 16** app (App Router). Notable choices:

- **Auth gate** via [`proxy.ts`](apps/web/src/proxy.ts). (In Next.js 16, the old `middleware.ts`
  was renamed to `proxy.ts` — a good example of why we read the *installed* docs instead of
  trusting memory.) It redirects unauthenticated users from `/dashboard` and `/canvas` to
  `/sign-in`.
- A **dev auth seam**: [`auth.ts`](apps/web/src/lib/auth.ts) reads a simple signed cookie for
  now. Real auth (Clerk) drops in here later without touching the rest of the app — the whole
  app depends only on `getSession()`.
- Pages: a dashboard (shows live API status) and an empty `/canvas` (React Flow mounted with no
  nodes yet — the palette arrives in Phase 2).

### 4.6 CI + the Phase 0 gate

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs lint → drift check → typecheck →
  DB migrate → pytest → Playwright on every push.
- The **gate** is a Playwright test ([`phase0.spec.ts`](e2e/tests/phase0.spec.ts)) that drives a
  real browser: unauthenticated → redirected to sign-in → click "Continue" → lands on dashboard,
  and `/health` returns ok. Playwright even boots the web + API servers for you.

> **Why a "gate" per phase?** It's a definition of done you can't fudge. If the gate passes, the
> phase genuinely works end-to-end, not just "the code looks right."

---

## 5. Phase 1 — The Engine

**Goal:** prove the hardest, riskiest part *before* building UI on top of it. By the end, a
hardcoded `Input → Agent → Output` graph **compiles and runs against a real LLM**, streaming its
reply — all driven by a test. No canvas needed yet.

We'll go through the five pieces in dependency order, then trace one request end-to-end.

### 5.1 The core idea: a typed state graph

Everything in the engine serves this model:

- **State** — a dictionary of named **channels** (e.g. `input`, `messages`, `output`).
- **Channels have reducers** — a *reducer* says how new writes combine with old values.
  The `messages` channel uses an **append** reducer (new messages are *added* to the list);
  most channels use **last-write-wins** (a new value replaces the old).
- **Nodes** read the state and return a partial update.
- **Edges** are pure control flow: "after node A, run node B."

This maps 1:1 onto LangGraph, which is exactly why we chose this model over the "wire every
value between boxes" style some no-code tools use.

### 5.2 The model layer (`services/model`) — the swappable LLM seam

Before nodes can think, they need a way to call an LLM. We define **one tiny interface** and
write adapters behind it:

```python
# services/model/.../base.py  (simplified)
class ModelClient(Protocol):
    def stream(self, *, model, messages, system="", tools=None, ...) -> AsyncIterator[StreamEvent]: ...
```

A call yields a sequence of **events** ([`events.py`](services/model/src/calypr_model/events.py)):
`TextDelta` (a chunk of text), `ToolCall`, `Usage` (token counts), and a final `Done`.

Three implementations exist:

- [`FakeModelClient`](services/model/src/calypr_model/fake.py) — deterministic, **needs no API
  key**. This is what tests and CI use, so they're fast, free, and reliable.
- [`OpenAIModelClient`](services/model/src/calypr_model/openai_client.py) — real OpenAI.
- [`AnthropicModelClient`](services/model/src/calypr_model/anthropic_client.py) — real Anthropic.

> **Lesson — program to an interface, not a vendor.** Because nodes/compiler/runtime only know
> about `ModelClient`, we added OpenAI *after the fact* with **zero changes** to any of them.
> The model layer is intentionally provider-agnostic (it doesn't even import LangChain).

> **Streaming, explained:** instead of waiting for the whole answer, the LLM sends text in small
> chunks as it's generated. We pass those chunks straight through so the UI can show the reply
> appearing live. That's what `AsyncIterator[StreamEvent]` enables.

### 5.3 The node registry (`packages/nodes`) — the plugin backbone

A **registry** is a lookup table of node types. Each node type registers *once* with everything
the system needs to know about it:

```python
# packages/nodes/.../registry.py  (simplified)
class BaseNode:
    type: str                 # e.g. "agent"
    meta: NodeMeta            # label/icon/category for the canvas palette
    config_model: type[BaseModel]   # the typed config schema for this node
    def reads(cfg) -> list[str]: ...   # which state channels it reads
    def writes(cfg) -> list[str]: ...  # which it writes
    def compile(cfg, ctx) -> NodeFn: ...  # turn config into a runnable node function
```

Registering a class with `@register` is all it takes for the compiler to handle it (and, in
Phase 2, for the canvas to render it). **Adding a new block type = adding one file.** No changes
to the compiler.

The three built-in nodes:

- [`InputNode`](packages/nodes/src/calypr_nodes/input.py) — the entry; takes the user's text
  from the `input` channel and appends it to `messages` as a *Human* message.
- [`AgentNode`](packages/nodes/src/calypr_nodes/agent.py) — **the hero**. Reads `messages`, calls
  the model (streaming each token out), and appends the model's reply. It already contains a
  *tool loop* structure (call model → run tools → repeat) — Phase 1 just runs it with zero tools,
  so it resolves in one model call. Phase 3 fills in tool execution.
- [`OutputNode`](packages/nodes/src/calypr_nodes/output.py) — the terminal; reads the last
  message and writes its text to the `output` channel.

> **Why "Agent" is special:** an LLM call is one thing; an *agent* is an LLM in a loop that can
> call tools and react to results. One Agent node, fully configured, is a complete agent by
> itself — that's why the MVP is "Agent-first."

### 5.4 The compiler (`services/compiler`) — the IP

This turns a `GraphSpec` (data) into an executable LangGraph graph. Two steps:

**1. Validate** ([`validate.py`](services/compiler/src/calypr_compiler/validate.py)) — returns a
list of `Issue`s, each tied to a node or edge id, so the canvas can highlight problems. It checks
for: unknown node types, invalid config, dangling edges, missing entry/output, dead-ends,
unreachable nodes, etc. If there's any *error*, the compiler refuses to build.

**2. Build** ([`compile.py`](services/compiler/src/calypr_compiler/compile.py)):

```python
# (simplified)
state_type = build_state_type(spec.state)      # dynamic typed state from the channels
builder = StateGraph(state_type)
for node in spec.nodes:                         # each node → registry → a runnable function
    cfg = get_node(node.type).config_model.model_validate(node.config)
    builder.add_node(node.id, get_node(node.type).compile(cfg, ctx))
builder.add_edge(START, spec.entry)             # wire control flow
for edge in spec.edges:
    builder.add_edge(edge.source, edge.target)
for node in spec.nodes:
    if node.type == "output":
        builder.add_edge(node.id, END)
return builder.compile(checkpointer=checkpointer)
```

[`state.py`](services/compiler/src/calypr_compiler/state.py) is a neat trick: it builds a Python
type *dynamically* from the declared channels, attaching the right reducer to each (the
`messages` channel gets LangGraph's `add_messages`). LangGraph reads that type to set up the
state.

[`golden.py`](services/compiler/src/calypr_compiler/golden.py) holds the canonical
`input_agent_output()` fixture — the "hello world" graph used throughout the tests.

### 5.5 The runtime (`services/runtime`) — run, stream, remember

[`run.py`](services/runtime/src/calypr_runtime/run.py) exposes two functions:

- `run(...)` → compile + run to completion, return the final state.
- `run_stream(...)` → compile + run, **yielding token events** as they arrive, then a final event.

It also wires a **checkpointer** ([`checkpoint.py`](services/runtime/src/calypr_runtime/checkpoint.py)):

> **Checkpointer, explained:** LangGraph can *save the state of a run* after each step, keyed by a
> `thread_id`. This gives you **durable memory** (resume a conversation later) and is what makes
> *human-in-the-loop* possible (pause for approval, resume). We use an in-memory checkpointer for
> tests and an **AsyncPostgresSaver** (backed by our Postgres) for real, durable runs.

### 5.6 Tracing one request end-to-end

This is the payoff. Here's what happens when you run the demo with the message `"hello"`:

```
run_stream(spec, ctx, "hello")
        │
        ▼
compile_graph(spec) ──► validate ──► StateGraph(Input → Agent → Output)
        │
        ▼  invoke with initial state {"input": "hello"}
┌───────────────────────────────────────────────────────────────────┐
│ START → Input node:                                                │
│    reads state["input"] = "hello"                                  │
│    returns {"messages": [HumanMessage("hello")]}   (append reducer)│
│                                                                    │
│        → Agent node:                                               │
│    reads state["messages"]                                         │
│    calls ModelClient.stream(...)  ──► OpenAI/Anthropic/Fake        │
│       for each TextDelta: writer({"type":"token","text": ...}) ────┼──► streamed to you
│    returns {"messages": [AIMessage("...the reply...")]}            │
│                                                                    │
│        → Output node:                                              │
│    reads the last message, returns {"output": "...the reply..."}   │
│                                                                    │
│ → END                                                              │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
final event: { output: "...the reply..." }   +   state saved by the checkpointer
```

The tokens stream out *while* the Agent node is still running, via LangGraph's "custom stream
writer." The final `output` channel is what a caller (or the playground, in Phase 2) shows as the
answer.

### 5.7 The Phase 1 gate

[`test_run.py`](services/runtime/tests/test_run.py) is the gate: it loads the golden spec,
compiles it, runs it with the `FakeModelClient`, and asserts the streamed tokens and final output
match. There's also a multi-turn test proving the checkpointer accumulates history, and a
Postgres test proving durable checkpointing against the real database.

---

## 6. Running & testing it yourself

Prerequisites: Node ≥ 20 (with Corepack for pnpm), Python 3.12 via [uv](https://docs.astral.sh/uv/),
Docker. One-time setup is already done in this repo; the everyday commands:

```bash
# 1. Make sure Postgres is up (idempotent)
docker compose -f infra/docker/compose.yaml up -d --wait

# 2. Run the whole backend test suite (all phases)
uv run pytest                  # ~25 tests; live LLM tests skip unless a key is set

# 3. See the engine stream a reply (no key → fake model; with a key → real LLM)
uv run python -m calypr_runtime.demo "Explain RAG in one sentence"
#   Put OPENAI_API_KEY=... in a (gitignored) .env to use OpenAI automatically.

# 4. The web app + API (the Phase 0 shell)
uv run uvicorn calypr_api.main:app --reload --port 8000          # API
pnpm --filter @calypr/web exec next dev --port 3100              # Web → http://localhost:3100

# 5. The Phase 0 browser gate (boots both servers for you)
pnpm --filter @calypr/e2e test
```

**How a beginner should explore:** run command #3 first (instant feedback), then open
`services/runtime/.../run.py` and follow the imports backwards into the compiler, the nodes, and
the model layer. Set `CALYPR_PROVIDER=fake` to step through with a deterministic model.

---

## 7. Key design decisions (the "why" cheat-sheet)

| Decision | Why it matters |
|---|---|
| **State graph, not dataflow wiring** | Matches LangGraph 1:1, so the compiler stays simple and branches/loops/memory are natural. |
| **One source of truth for the DSL (Pydantic → TS)** | The canvas (TS) and engine (Python) can never silently disagree; CI enforces it. |
| **Node registry (plugin pattern)** | New block types are *plugins* — one file, no compiler edits. This is what makes a future marketplace additive, not a rewrite. |
| **Thin `ModelClient` interface** | Swap or add LLM providers without touching the engine (we proved this by adding OpenAI later). |
| **Fake model for tests** | CI is fast, free, and deterministic; real-provider tests skip without keys. |
| **Agent node as the hero** | One configured Agent is a complete agent — the fastest path to "build a working agent." |
| **Build the engine before the canvas** | The compiler is the riskiest part; prove it headless so the canvas (Phase 2) is "just" UI over a working spine. |

---

## 8. What's next (Phase 2 preview)

Phase 2 makes the canvas real: a **node palette** (drag Input/Agent/Output), connect them, an
**Agent config panel** (model, prompt), **save** to a `GraphSpec`, and a **playground** to chat
with your agent — all backed by the engine you just read about. The empty `/canvas` you see today
becomes a working builder.

---

## 9. Mini-glossary

- **Monorepo** — one git repo holding multiple related projects (packages).
- **Workspace** — a manager's view of those packages (pnpm for JS, uv for Python).
- **DSL** (Domain-Specific Language) — here, our JSON description of a graph (`GraphSpec`).
- **Pydantic** — Python library for typed, validated data models.
- **LangGraph** — library for building agents as state graphs.
- **State / channel / reducer** — the shared data, a named field in it, and the rule for merging writes.
- **Node / edge** — a unit of work / a control-flow connection between nodes.
- **Compiler** — code that turns our `GraphSpec` into a runnable LangGraph graph.
- **Checkpointer** — LangGraph's mechanism to save/restore run state (durable memory, resumable runs).
- **Streaming** — sending the LLM's answer in chunks as it's produced.
- **Migration (Alembic)** — a versioned, repeatable change to the database schema.
- **RLS (Row-Level Security)** — Postgres feature that filters rows per tenant at the database level.
- **CI gate** — an automated test that must pass to consider a phase "done."

