# Calypr — Walkthrough (Phases 0–5)

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
   A user's drawing                Our job                    What runs / what you own
 ┌───────────────────┐    ┌──────────────────────┐    ┌──────────────────────────┐
 │ Input → Agent →   │ →  │ DSL (a JSON spec)    │ →  │ LangGraph StateGraph     │
 │        Output     │    │ → Compiler / Codegen │    │ → streams a reply        │
 └───────────────────┘    └──────────────────────┘    │ → ownable Python (LangGraph) │
   (Phase 2 — done)         (Phases 1, 3 — done)       └──────────────────────────┘
```

This document builds the **foundation** (Phase 0), the **engine** (Phase 1), the **visual
canvas** (Phase 2), the **code altitude** (Phase 3 — every graph also generates Python you
own), **agent types + control flow** (Phase 4 — branching, loops, the agent ladder), and
**tools + ReAct/Reflexion** (Phase 5). As of Phase 5 you can draw — or start from a template —
a tool-using agent, chat with it backed by real OpenAI/Anthropic models, and open a **Code**
view to get the idiomatic LangGraph it compiles to.

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
│   ├── api/          # FastAPI: /compile, /runs (SSE), /agents (calypr-api)
│   └── web/          # Next.js: canvas, playground, proxies (@calypr/web)
├── packages/
│   ├── dsl/          # GraphSpec contract     (calypr-dsl + @calypr/dsl)  ← the contract
│   └── nodes/        # node registry + types  (calypr-nodes)              ← the plugin backbone
│                     #   input, agent, output, code, router, evaluator,
│                     #   memory, tool, responder, revisor (+ a tools catalog)
├── services/
│   ├── model/        # ModelClient + OpenAI/Anthropic/fake (calypr-model) ← the LLM seam
│   ├── compiler/     # GraphSpec → StateGraph + templates  (calypr-compiler) ← the IP
│   ├── codegen/      # GraphSpec → ownable Python          (calypr-codegen)  ← the wedge
│   └── runtime/      # run + stream + memory  (calypr-runtime)
├── e2e/              # Playwright gates: phase0–phase5 (@calypr/e2e)
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
  extension** (we'll need vector search for RAG / knowledge bases later) in a container.
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
  so it resolves in one model call. Phase 5 fills in tool execution (ReAct).
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

## 6. Phase 2 — The Canvas & Playground

**Goal:** the empty canvas becomes a real builder — drag blocks, configure them, and chat
with the agent you drew. This is the MVP proof.

Phase 2 connects the **web front end** to the **Python engine**. Crucially, it adds *no new
agent logic* — it's a thin UI + HTTP skin over the Phase 1 engine. Three new pieces: the
canvas (front end), the API endpoints (back end), and the streaming plumbing between them.

### 6.1 The canvas (React Flow)

[React Flow](https://reactflow.dev) is a library for node-and-edge canvases. We give it:

- **Custom node components** ([`nodes.tsx`](apps/web/src/components/canvas/nodes.tsx)) — how
  each block (Input/Agent/Output) looks, with the little dots (*handles*) you connect.
- A **palette** ([`Palette.tsx`](apps/web/src/components/canvas/Palette.tsx)) — buttons that add
  a block; adding one auto-links it after the previous, so a few clicks build a chain.
- A **config panel** ([`ConfigPanel.tsx`](apps/web/src/components/canvas/ConfigPanel.tsx)) —
  select the Agent to pick its model, system prompt, and step cap.

> **Beginner note — the canvas is just state.** React Flow holds two arrays: `nodes` and
> `edges`. Clicking "+ Agent" pushes a node; connecting two handles pushes an edge. Everything
> you see is a render of those two arrays ([`canvas/page.tsx`](apps/web/src/app/canvas/page.tsx)).

### 6.2 From canvas to contract (the key bridge)

The canvas's nodes/edges aren't the same shape as the engine's `GraphSpec`.
[`buildGraphSpec()`](apps/web/src/lib/graph.ts) translates one into the other — and it imports
the **generated `@calypr/dsl` types**, so the object it builds is exactly what the Python
engine expects.

> **This is where the Phase 0 codegen pays off.** The canvas (TypeScript) and the engine
> (Python) agree on `GraphSpec` because both sides use types generated from the *same* Pydantic
> source. The UI literally can't build a graph of the wrong shape.

### 6.3 The API endpoints (`apps/api/routers`)

The engine gets three HTTP endpoints:

- `POST /compile` — validate a graph, return a list of issues (so the canvas can show errors).
- `POST /runs` — run a graph and **stream** the reply ([`runs.py`](apps/api/src/calypr_api/routers/runs.py)).
- `POST/GET /agents` — save/list agents; the `GraphSpec` is stored as JSON in Postgres, scoped
  to a tenant with RLS ([`agents.py`](apps/api/src/calypr_api/routers/agents.py)).

A small **provider factory** ([`factory.py`](services/model/src/calypr_model/factory.py)) picks
the LLM client from the agent's model id: `gpt-*` → OpenAI, `claude-*` → Anthropic, `fake` →
the deterministic stub. Adding a provider stays a one-file change.

### 6.4 Streaming over a proxy (SSE + a Next route)

How do tokens get from the Python engine to your browser, live?

- The Python `/runs` endpoint returns **Server-Sent Events (SSE)** — one long-lived HTTP
  response where the server writes `data: {...}` lines as things happen, ending with `[DONE]`.
- The browser doesn't call Python directly. It calls a **same-origin Next.js route**
  ([`app/api/runs/route.ts`](apps/web/src/app/api/runs/route.ts)) that forwards the request to
  Python and pipes the stream straight back. The client reader is in
  [`lib/api.ts`](apps/web/src/lib/api.ts).

> **Why the proxy?** Two reasons worth internalizing: (1) **no CORS headaches** — the browser
> only ever talks to its own origin; (2) **secrets stay server-side** — the API URL and provider
> keys live on the server, never shipped to the browser. This is the standard production shape.

> **SSE, explained:** a normal request gets one response, then closes. SSE keeps the response
> *open* and streams text chunks as they're produced. The browser reads them as they arrive —
> that's how you watch the reply type itself out.

### 6.5 Tracing a chat end-to-end (through the UI)

```
You type "hi" in the Playground and hit Send
        │
   buildGraphSpec(nodes, edges)            canvas → GraphSpec (the shared contract)
        │  POST /api/runs { graph, message, thread_id }
        ▼
Next route /api/runs  ── forwards ──►  Python POST /runs
        │                                     │
        │                       context_for(graph): "gpt-4o-mini" → OpenAIModelClient
        │                                     │  run_stream(graph, ctx, "hi")
        │                                     ▼  (the Phase 1 engine, unchanged!)
        │                            Input → Agent → Output, streaming tokens
        │  ◄── SSE: data:{"type":"token","text":"H"} … data:{"type":"final",…} ──
        ▼
Browser appends each token to the assistant bubble → you watch it type
```

The key insight: **the Agent runs exactly as it did in the headless Phase 1 demo.** We just
gave it a face and a pipe.

### 6.6 The Phase 2 gate

[`phase2.spec.ts`](e2e/tests/phase2.spec.ts) is the gate: a real browser signs in, clicks
**+Input / +Agent / +Output**, configures the Agent, opens the Playground, sends a message, and
asserts a streamed reply appears. It uses the `fake` model, so it needs no API key — fast and
deterministic in CI.

---

## 7. Phase 3 — Code Altitude (canvas → ownable Python)

**Goal:** the canvas stops being a black box. *Any* graph you draw also **generates idiomatic,
standalone Python (LangGraph)** with zero dependency on Calypr — code you could read, edit, and
merge. This is the strategic bet (see **[`WEDGE-PLAN.md`](./WEDGE-PLAN.md)**): an AI engineer
never hits a ceiling, because they can always drop down to the code they own.

### 7.1 A `codegen()` to mirror `compile()`

Phase 1's nodes had one job: `compile(cfg, ctx)` → a runnable function. Phase 3 gives every node
a **second, parallel job**: `codegen(cfg, fn_name)` → a **`CodeFragment`** (a chunk of Python
source + the imports it needs). The new **`services/codegen`** package
([`generate.py`](services/codegen/src/calypr_codegen/generate.py)) walks the graph, collects each
node's fragment, builds a `State` TypedDict from the channels, dedupes + groups imports, and
wires a `build_graph()` that assembles the `StateGraph`. The output is run through `ruff` so it
reads like a person wrote it. Each node now answers two questions — *how do I run?* (`compile`)
and *how do I look as code?* (`codegen`) — and they must agree.

### 7.2 The round-trip equivalence test (the real guarantee)

A pretty code generator is worthless if the code behaves differently from the canvas. The Phase 3
gate is a **round-trip equivalence test**: take a graph, run it in-memory (`compile()` + run),
then generate the Python, **import it as a real module, run that**, and assert the outputs match.
If they ever diverge, CI fails. That's what turns "the code you get is the code that ran" into a
guarantee instead of a hope.

### 7.3 The Custom Code node (the no-ceiling escape hatch)

The **Custom Code** node ([`code.py`](packages/nodes/src/calypr_nodes/code.py)) lets you write a
Python function body right on the canvas. It runs as-is in the engine, and `codegen()` emits it
**verbatim** into the generated module — so even a hand-written block round-trips. This is the
escape hatch: when no block exists for what you need, write the Python. (It executes arbitrary
code, so it's gated behind `CALYPR_ALLOW_CUSTOM_CODE=1` in trusted environments.)

### 7.4 The Code view

The canvas grows a **Code** panel ([`CodeView.tsx`](apps/web/src/components/canvas/CodeView.tsx))
backed by a `POST /codegen` endpoint — open it to see the live Python for whatever you've drawn.
Codegen is pure (no model call, no DB), so it needs no API key.

**Gate** ([`phase3.spec.ts`](e2e/tests/phase3.spec.ts)): build Input → Agent → Custom Code →
Output, open the Code view, and assert it's real LangGraph (`StateGraph`, `init_chat_model`) with
the custom code round-tripped in.

---

## 8. Phase 4 — Agent Types & Control Flow

**Goal:** go from "one Agent" to the classic **agent ladder**, and give the canvas real
**branching and loops**. The whole phase is a *capability ladder* built on one keystone.

### 8.1 Conditional control flow (the keystone)

Phase 1 wired only unconditional edges ("after A, run B"). Real agents make decisions. `EdgeSpec`
already had a `condition` field; Phase 4 makes the compiler honor it. A node's new **`routing()`**
method returns a *path function* `(state) → branch_name`; the compiler wires it with LangGraph's
**`add_conditional_edges`**, mapping each branch name to the target of the out-edge labelled with
that condition. `codegen()` emits the same. Loops fall out naturally (an edge can point back), and
a `recursion_limit` keeps them from running away.

### 8.2 The Router (If-Else) node

The first node built on the keystone:
[`router.py`](packages/nodes/src/calypr_nodes/router.py) picks a branch by **rules** — a safe
expression over state, gated like Custom Code (e.g. "if the input mentions 'refund', go left").
Its labelled out-edges become the conditional edges.

### 8.3 The agent ladder (`agent_type`)

The Agent grew an `agent_type` preset spanning the **Russell & Norvig taxonomy**: *simple-reflex*
(reacts to the latest input), *model-based* (uses the whole conversation), *goal-based* (plans
toward a goal), *utility-based* (generates N candidates, keeps the best), *learning* (adapts from
feedback), and *reflection* (an internal generate → critique → revise loop). Each preset scaffolds
the system prompt and emits matching idiomatic Python. *(In Phase 5 we removed the per-node
dropdown — you choose a type by starting from its **template** instead.)*

### 8.4 Capability nodes: Evaluator & Memory

- **Evaluator** ([`evaluator.py`](packages/nodes/src/calypr_nodes/evaluator.py)) — *LLM-as-judge*:
  scores an answer against a rubric and writes the score + rationale to state. It doubles as the
  eval/trust layer the wedge wants.
- **Memory** ([`memory.py`](packages/nodes/src/calypr_nodes/memory.py)) — a *visible* memory step:
  append each turn to a buffer, or summarize the conversation into long-term memory.

### 8.5 Templates (the starter gallery)

Archetype graphs ship as starter **templates**
([`templates.py`](services/compiler/src/calypr_compiler/templates.py)) served from
`GET /templates`, ordered simple → complex. Pick one from the canvas header and it hydrates the
board — a `graphToCanvas()` that inverts `buildGraphSpec()`.

**Gate** ([`phase4.spec.ts`](e2e/tests/phase4.spec.ts)): add an If-Else router and confirm the
Code view shows `add_conditional_edges`; load a template and confirm it projects to code.

---

## 9. Phase 5 — Tools, ReAct & Reflexion

**Goal:** give agents **tools**, then assemble two famous agent patterns from the primitives —
all still round-tripping to ownable code.

### 9.1 The Tool node + edge-driven binding

A **Tool** node ([`tool.py`](packages/nodes/src/calypr_nodes/tool.py)) wraps LangGraph's prebuilt
**`ToolNode`** over a provider (a dropdown: a deterministic `demo_search` that needs no key, plus
**Tavily** for real web search). The clever part is **edge-driven binding**: when you wire an
Agent → Tool, the compiler does two things — it **binds** that tool to the agent's model (so the
model can *call* it) *and* uses the Tool node to **execute** the calls. That mirrors how LangGraph
itself works: the bound tools and the ToolNode's tools are the same tools.

> **Secrets:** an API key you type on a Tool node is used at runtime only — generated code reads
> it from an environment variable (`TAVILY_API_KEY`) and **never embeds the secret**.

### 9.2 ReAct (reason + act)

With a tool wired, the Agent becomes a tiny **ReAct** loop: each turn it either asks for a tool
(→ the Tool node runs it → loop back) or answers (→ done). The branch is LangGraph's standard
**`tools_condition`** — and that's exactly what the generated code emits. The `tpl-react` template
is `Input → Agent ⇄ Tools → Output`.

### 9.3 Reflexion (research + self-revision)

**Reflexion** is reflection *grounded in tool use*. Two new actor nodes:

- **Responder** ([`responder.py`](packages/nodes/src/calypr_nodes/responder.py)) — answers,
  critiques its own answer (what's missing / superfluous), and searches for the gaps.
- **Revisor** ([`revisor.py`](packages/nodes/src/calypr_nodes/revisor.py)) — improves the answer
  using the search results and **counts revisions**. Its `routing()` makes the loop **bounded**:
  keep revising (→ Tools → Revisor) until `max_revisions`, then finish (→ Output).

The `tpl-reflexion` template is `Input → Responder → Tools → Revisor → (revise loop | Output)`.
The counter plus the `recursion_limit` guarantee termination.

> **ReAct vs Reflexion:** ReAct interleaves *thinking and acting* until it can answer. Reflexion
> adds a *self-critique loop* — answer, research, revise, repeat — to raise quality. On the canvas
> both are just nodes + conditional edges, and both generate canonical LangGraph you own.

**Gate** ([`phase5.spec.ts`](e2e/tests/phase5.spec.ts)): load the ReAct template → the Code view
shows `ToolNode` + `tools_condition`; load Reflexion → it shows the Responder/Revisor and the
bounded `route_node_revisor` loop; the Tool node shows its provider dropdown + key field; and the
Agent panel no longer has a type dropdown.

---

## 10. Running & testing it yourself

Prerequisites: Node ≥ 20 (with Corepack for pnpm), Python 3.12 via [uv](https://docs.astral.sh/uv/),
Docker. One-time setup is already done in this repo; the everyday commands:

```bash
# 1. Make sure Postgres is up (idempotent; only needed to *save* agents)
docker compose -f infra/docker/compose.yaml up -d --wait

# 2. Run the whole backend test suite (all phases)
uv run pytest                  # ~90 tests; live LLM tests are opt-in (CALYPR_RUN_LIVE_TESTS=1)

# 3. See the engine stream a reply (no key → fake model; with a key → real LLM)
uv run python -m calypr_runtime.demo "Explain RAG in one sentence"
#   Put OPENAI_API_KEY=... in a (gitignored) .env to use OpenAI automatically.

# 4. The full app — boots BOTH servers (api :8000 + web :3100); Ctrl-C stops both
./start.sh
#   → sign in → Open canvas → pick a template (e.g. ReAct) or +Input +Agent +Output
#   → Playground to chat, or Code to see the ownable Python it compiles to

# 5. The browser gates (Phases 0–5; boots both servers for you). Router/Custom Code
#    use eval, so the gate sets CALYPR_ALLOW_CUSTOM_CODE=1.
CALYPR_ALLOW_CUSTOM_CODE=1 pnpm --filter @calypr/e2e test
```

**How a beginner should explore:** run command #3 first (instant feedback), then open
`services/runtime/.../run.py` and follow the imports backwards into the compiler, the nodes, and
the model layer. To see the *Phase 2* path, trace a chat **front-to-back**:
[`Playground.tsx`](apps/web/src/components/canvas/Playground.tsx) → [`lib/api.ts`](apps/web/src/lib/api.ts)
→ [`app/api/runs/route.ts`](apps/web/src/app/api/runs/route.ts) → [`routers/runs.py`](apps/api/src/calypr_api/routers/runs.py)
→ `run_stream`. To see the *Phase 3* payoff, load a template, open the **Code** view, and read the
generated module — then find the node whose `codegen()` produced each function. Set the model to
`fake` to step through deterministically.

---

## 11. Key design decisions (the "why" cheat-sheet)

| Decision | Why it matters |
|---|---|
| **State graph, not dataflow wiring** | Matches LangGraph 1:1, so the compiler stays simple and branches/loops/memory are natural. |
| **One source of truth for the DSL (Pydantic → TS)** | The canvas (TS) and engine (Python) can never silently disagree; CI enforces it. |
| **Node registry (plugin pattern)** | New block types are *plugins* — one file, no compiler edits. This is what makes a future marketplace additive, not a rewrite. |
| **Thin `ModelClient` interface** | Swap or add LLM providers without touching the engine (we proved this by adding OpenAI later). |
| **Fake model for tests** | CI is fast, free, and deterministic; real-provider tests skip without keys. |
| **Agent node as the hero** | One configured Agent is a complete agent — the fastest path to "build a working agent." |
| **Build the engine before the canvas** | The compiler is the riskiest part; prove it headless so the canvas (Phase 2) is "just" UI over a working spine. |
| **Next route proxy for the API** | The browser talks same-origin (no CORS), and the API URL + provider keys stay server-side. Production-shaped from day one. |
| **Canvas → GraphSpec via the shared types** | The UI builds the *exact* object the engine compiles — the Phase 0 codegen contract closes the loop end-to-end. |
| **`codegen()` mirrors `compile()` + a round-trip test** | The canvas projects to *ownable* Python that provably runs the same — the no-ceiling wedge, enforced in CI. |
| **Conditional edges via `routing()`** | One keystone (`add_conditional_edges`) gives the canvas branching *and* loops — every later pattern (Router, ReAct, Reflexion) reuses it. |
| **Edge-driven tool binding** | Wiring Agent → Tool both binds the tool and executes it — the same tool list, exactly like LangGraph; ReAct is "just" that loop. |
| **Patterns as compositions, types as templates** | ReAct/Reflexion are nodes + edges (not bespoke engines), and the agent ladder lives in templates — so the canvas stays small and the generated code stays canonical. |

---

## 12. What's next

Phases 0–5 prove the **prompt → canvas → code** wedge end-to-end: you can draw (or start from a
template) a tool-using agent, run it, and walk away with idiomatic LangGraph you own. What's still
ahead (see **[`CLAUDE-PLAN.md`](./CLAUDE-PLAN.md)** / **[`WEDGE-PLAN.md`](./WEDGE-PLAN.md)**):

- **Knowledge bases (RAG):** upload documents → chunk → embed → store in **pgvector**; an agent
  retrieves relevant passages and answers **with citations**. (This is why we chose pgvector back
  in Phase 0.) More tool providers land alongside — an HTTP-request tool and an **MCP client**, so
  any [MCP](https://modelcontextprotocol.io) server's tools become available — and real Tavily
  execution (today it's codegen-only).
- **Phase 6 — multi-agent:** supervisor/worker and hand-off graphs, composing the single agents
  from Phases 4–5 into teams — still on the same state-graph + codegen spine.
- **Per-node models + richer playground:** each LLM node resolves its own provider (a cheap
  Responder + a strong Revisor), and the playground surfaces tool-call steps and citations so you
  see *how* the agent reached its answer.

Same discipline throughout: every new node ships a `codegen()` so the round-trip keeps holding,
and each phase lands behind a Playwright gate.

> **RAG, explained:** *Retrieval-Augmented Generation* means: before answering, fetch relevant
> snippets from your documents and hand them to the model as context. It lets an agent answer
> from *your* data (with citations) instead of only what the model memorized.

---

## 13. Mini-glossary

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
- **React Flow (xyflow)** — the library that renders the node-and-edge canvas; its state is just `nodes` + `edges` arrays.
- **SSE (Server-Sent Events)** — one long-lived HTTP response the server streams `data:` chunks over until done.
- **Proxy (Next route)** — a same-origin server endpoint that forwards to the Python API (hides keys, avoids CORS).
- **Provider factory** — code that picks the LLM client (OpenAI / Anthropic / fake) from a model id.
- **Codegen / round-trip** — generating ownable Python from a graph; the *round-trip test* proves the generated code runs identically to the in-memory engine.
- **`codegen()`** — a node's "how do I look as code?" method, mirroring `compile()` ("how do I run?").
- **Conditional edges (`routing()` / `add_conditional_edges`)** — control flow that branches (and loops) on a path function over state, instead of always running the next node.
- **Agent ladder / `agent_type`** — the Russell & Norvig presets (simple-reflex, model-based, goal-based, utility-based, learning, reflection) a single Agent can take.
- **Router (If-Else)** — a node that branches by a rule over state; **Evaluator** — LLM-as-judge (score + rationale); **Memory** — a visible buffer/summary step.
- **Tool node / `ToolNode`** — runs the tools an agent calls; **edge-driven binding** — wiring Agent → Tool both *binds* the tool to the model and *executes* its calls.
- **ReAct** — an agent that loops *reason → act (tool) → observe* until it can answer (`tools_condition`). **Reflexion** — answer, research, and *revise* in a bounded loop (Responder + Revisor).
- **Template** — a ready-to-run starter graph (e.g. ReAct, Reflexion) served from `GET /templates` and loaded onto the canvas.
- **RAG (Retrieval-Augmented Generation)** — fetch relevant document snippets first, then answer from them (with citations). Still ahead (see §12).
- **Migration (Alembic)** — a versioned, repeatable change to the database schema.
- **RLS (Row-Level Security)** — Postgres feature that filters rows per tenant at the database level.
- **CI gate** — an automated test that must pass to consider a phase "done."

