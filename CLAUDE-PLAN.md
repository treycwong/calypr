# Calypr — Foundational Building Blocks Architecture (MVP)

## Context

Calypr is a multi-tenant SaaS where users design AI agents on a visual canvas that
compiles to **LangGraph** and runs in a hosted runtime. `PLAN.md` and `MVP.md` already
establish a strong high-level architecture (stack, data model, phased roadmap, growth
plan). What they **name but do not specify** is the thing this task is about: the
**foundational building blocks** — the nodes and tools a user drags onto the canvas to
assemble an end-to-end agent — and the contracts that bind canvas → DSL → compiler →
runtime together.

This plan specifies those building blocks in depth and makes three structural decisions
the existing docs leave implicit. It is additive to `PLAN.md`/`MVP.md`, not a rewrite of
them. The repo is greenfield (only the two markdown docs exist today), so "files to
modify" below are the foundational files to **create**.

### Decisions locked with the user (this session)

| Fork | Choice | Consequence for this plan |
|------|--------|---------------------------|
| Stack/language | **Python LangGraph + TS canvas (as planned)** | DSL source of truth is **Pydantic → generated TS**. The codegen contract must be enforced in CI (drift = build break). |
| LLM layer | **Thin swappable interface, decide later** | A minimal `ModelClient` protocol with **one** provider adapter to start (e.g. Anthropic Claude). Tool-calling + streaming are in-scope from day one (the Agent loop needs them); routing/failover/caching/metering are deferred — but a `usage` hook seam is stubbed so metering is additive. **No AI Gateway in MVP.** |
| First slice | **Agent node first** | The thinnest end-to-end milestone is `Input → Agent → Output`, where the Agent block alone (model + tools + knowledge base + tool loop) is a complete agent. Build order is Agent-centric. |

---

## 1. The mental model (one paragraph that governs everything)

A Calypr agent is a **typed state graph**. There are exactly three primitives plus one
cross-cutting concept:

- **State** — a typed, shared object (LangGraph *channels*) that flows through the graph. Defined in a **State editor**.
- **Nodes** — units of work that *read* state, do something, and *write* state. Dragged from the palette.
- **Edges** — **control flow only** (which node runs next). Sequential, conditional (Router), and — post-MVP — parallel/loop.
- **Tools** — typed capabilities an **Agent/LLM** node may *call inside its own reasoning loop*. Tools are **not** vertices on the control-flow graph.

Matching the canvas paradigm to the runtime paradigm (a state graph) is what keeps the
compiler tractable and the IP defensible. Everything below follows from this.

## 2. Three structural decisions (the improvements over PLAN.md/MVP.md)

### 2.1 Node vs. Tool — a hard distinction

The existing docs list `Tool` in the same flat list as `LLM`, `Router`, etc. Conflating
these is the #1 UX failure mode of Langflow/Flowise. We separate them:

- A **Node** is a vertex in control flow — the graph decides *when* it runs.
- A **Tool** is a capability an **Agent** node invokes *during* its tool loop — the *model* decides whether/when to call it.
- A **Tool node** exists too, but only for the *deterministic* case ("always call this one tool here"). Autonomous tool use lives **inside** the Agent node.

This keeps the canvas readable: the graph shows orchestration; tools are configured *on*
the Agent that uses them.

### 2.2 State-channel paradigm, not dataflow wiring

Two canvas paradigms exist; we commit to one:

- ❌ **Dataflow wiring** (Flowise/Langflow): every value is wired port→port. Produces spaghetti, fights loops/branches/shared memory, and does **not** map to LangGraph's state model.
- ✅ **State channels** (LangGraph-native): edges carry control only; nodes read/write a shared typed state by **name**. Maps 1:1 to the runtime; clean for branches, loops, and multi-agent.

We choose **state channels**. The known downside (data dependencies are less visually
obvious) is mitigated in the canvas, not the model: a **State/Variables panel**,
`{{state.x}}` autocomplete in every config field, and read/write highlighting when a node
is selected. (We may later add a few optional "data pins" as sugar that compile to a
state write+read pair — but the canonical model is named state.)

### 2.3 Node registry as a plugin system (the extensibility backbone)

Every node type, tool, and template is a **plugin registered once**, not hardcoded into
the canvas or compiler. This is what makes the post-MVP marketplace/SDK (`MVP.md`
Workstream C) *additive instead of a rewrite* — and it directly delivers `MVP.md`'s "one
next action" (clean node-type registry + connector abstraction). A node registration
bundles: metadata, a config schema, read/write declarations, a compile function, and an
optional validator (see §5).

---

## 3. The node taxonomy (the building blocks)

Grouped by role (better UX + architecture than a flat list). **MVP** column marks what
ships in the first slice vs. later phases.

| Category | Block | What it does | Compiles to | MVP |
|----------|-------|--------------|-------------|-----|
| **I/O & Control** | **Input / Trigger** | Entry point; defines the input contract; seeds state. Variants: chat, API, form (scheduled/webhook later). | graph entrypoint + initial channels | ✅ |
| | **Output / Response** | Terminal; selects which channel(s) to return/stream. | `END` + output selection | ✅ |
| | **Router / Branch** | Conditional routing (rules **or** LLM classifier) over outgoing edges. | `add_conditional_edges` | ✅ |
| | Parallel / Loop | Fan-out+join; map/while. | cyclic/concurrent edges + guard | ◻ later |
| **Reasoning** | **★ Agent** | **The hero.** Model + system prompt + attached **tools** + attached **KBs** + tool loop + memory + step cap. *One Agent node = a complete E2E agent.* | ReAct-style **subgraph** (tool loop) | ✅ |
| | **LLM / Prompt** | Single deterministic model call; templated prompt; text or structured output. The simpler cousin of Agent, for pipeline steps. | single model-call node | ✅ |
| | Classifier / Extractor | Structured-output presets (sugar over LLM). | LLM node w/ fixed schema | ◻ later (as presets) |
| **Knowledge & Memory** | **Retriever (RAG)** | Explicit query of a Knowledge Base → ranked chunks + citations into state. | retriever bound to pgvector KB | ✅ |
| | **Memory** | Read/write conversational or long-term memory (thread/user/workspace scope). | checkpointer-backed state (+ vector store later) | ✅ (thread) |
| **Tools & Actions** | **Tool node** | Invoke **one specific** tool deterministically (input mapped from state). | tool-executor node | ✅ |
| **Orchestration** | **Sub-agent** | Embed another compiled agent as a node (composition). | compiled subgraph | ◻ Phase 5 |
| | **Supervisor** | Router-agent delegating to a worker team + aggregating. | supervisor graph + worker subgraphs + handoff | ◻ Phase 5 |
| | **Human-in-the-loop / Approval** | Pause for human input/approval; resume. | `interrupt()` + resume API | ◻ Phase 5 |
| **Glue / Utility** | Transform / Map | No-code field mapping / safe expression (sandboxed code-interpreter **deferred** — security cost). | small deterministic node | ◻ later |
| | Guard / Filter | Validation, PII redaction, moderation. | guard node | ◻ later |

**The Agent node config** (concrete — it's the hero of the first slice):

```python
class AgentConfig(BaseModel):
    model: ModelRef                       # provider + name + params (temperature, max_tokens)
    system_prompt: str                    # templated, references {{state.x}}
    input_channel: str = "messages"       # what it consumes
    output_channel: str = "messages"      # where it writes (append reducer)
    tools: list[ToolRef] = []             # from the tool registry (§6)
    knowledge_bases: list[KBRef] = []     # auto-wrapped as retrieval tools → agentic RAG
    max_steps: int = 8                    # tool-loop cap (a cost guard, on by default)
    memory: MemoryConfig | None = None    # thread/user scope
    stop_when: Literal["no_tool_calls"] = "no_tool_calls"
    response_format: Literal["text"] | JsonSchema = "text"
```

It compiles to a ReAct-shaped subgraph: bind model with tools → if the model emits tool
calls, run them via a tool node → loop until no tool calls or `max_steps` → write the
final result to `output_channel`. Knowledge bases are auto-wrapped as retrieval tools so
the agent decides when to retrieve. (Built behind our compiler interface, not by exposing
LangChain to the user — per `PLAN.md` §9 "minimize LangChain exposure.")

**Input** seeds state (`mode: chat|api|form`, `input_schema`). **Output** selects
channels to return/stream. Together with Agent they form the thinnest complete agent:
`Input → Agent → Output`.

## 4. The state model

State is a typed dict of **channels**, each `{key, type, reducer, default}`. The
`reducer` defines how iterative/concurrent writes merge — e.g. `messages` uses an
**append** reducer; scalars use last-write-wins. This is LangGraph's
`Annotated[type, reducer]`. The **State editor** in the canvas defines channels; default
channels for a chat agent are `messages` (append), `input`, `output`, plus `context` /
`citations` for RAG. Each node declares `reads`/`writes` in its registry metadata, which
powers validation (§5) and canvas highlighting (§2.2).

## 5. The node registry (plugin backbone)

Each node type registers once (Python; the same shape generalizes to tools and
templates):

```python
@register_node("agent")
class AgentNode:
    meta = NodeMeta(label="Agent", category="reasoning", icon="bot", description="...")
    config_schema = AgentConfig                       # → drives the canvas config panel via codegen
    def reads(cfg):  return [cfg.input_channel, *channels_in(cfg.system_prompt)]
    def writes(cfg): return [cfg.output_channel]
    def compile(cfg, ctx) -> RunnableNode: ...        # emits the LangGraph node / subgraph
    def validate(cfg, graph) -> list[Issue]: ...      # optional node-specific checks
```

Registering a node makes it appear in the palette, validate, compile, and render its
config panel — **no other code changes**. This is the single most important
extensibility decision in the system.

## 6. The unified Tool interface ("tools the agent can use")

One shape for **every** capability, so built-in tools, KB retrieval, MCP servers, and
sub-agents are not five special cases:

```python
class Tool(BaseModel):
    name: str
    description: str                      # what the model sees (function-calling)
    input_schema: JsonSchema
    output_schema: JsonSchema | None = None
    auth: CredentialRef | None = None     # envelope-encrypted, injected at runtime, NEVER in the DSL
    source: Literal["builtin", "kb", "mcp", "subagent", "connector"]
    async def run(self, input, ctx) -> ToolResult: ...
```

- **Built-in (MVP):** HTTP request, web search, calculator/current-time.
- **Knowledge-base-as-tool (MVP):** a KB wrapped as a retrieval tool → agentic RAG.
- **MCP (build the abstraction MCP-shaped now):** an MCP client adapter maps any MCP server's tools into `Tool` objects. Cheap insurance that makes `MVP.md`'s "MCP client" workstream nearly free later; LangGraph already speaks MCP.
- **Sub-agent-as-tool (Phase 5):** a compiled agent exposed via the same interface → "agents calling agents," an alternative to the supervisor.
- **Native connectors (post-MVP):** Shopify/Klaviyo/etc. — same `Tool` interface, just more sources.

Credentials live in a per-workspace, envelope-encrypted vault and are injected at runtime;
they are **never** serialized into the DSL.

## 7. The DSL (the load-bearing contract)

A versioned JSON document; **Pydantic is the source of truth**, TS is generated.

```python
class GraphSpec(BaseModel):
    schema_version: str                   # e.g. "1.0" — versioned for forward-compat
    id: str; name: str; description: str = ""
    state: list[StateChannel]             # {key, type, reducer, default}
    nodes: list[NodeSpec]                 # discriminated by `type`; `config` validated by the node's registry schema
    edges: list[EdgeSpec]                 # control flow: {source, target, condition?}
    entry: NodeId
    tool_bindings: list[ToolBinding] = [] # workspace tool refs the graph uses
```

**Codegen discipline (mandatory, because we kept the Python/TS split):** Pydantic →
JSON Schema → TS types. A CI check regenerates the TS and **fails the build if it drifts**
from the committed output. Golden DSL fixtures (a handful of representative `GraphSpec`
JSON files) are validated by both the Python compiler and the TS canvas in CI. This is
the concrete mitigation for the risk `PLAN.md` itself flags as #1.

## 8. The compiler (DSL → StateGraph) + validation

1. Build a `StateGraph` with channels + reducers from `state[]`.
2. For each node: `registry[node.type].compile(node.config, ctx)`. Agent/Sub-agent compile to **subgraphs**.
3. Add edges; **Router** → `add_conditional_edges(routing_fn)`.
4. Resolve `tool_bindings` → `Tool` objects (inject creds); bind retrievers → KB; sub-agents → compiled subgraphs.
5. HITL → `interrupt()`; resume via API + checkpointer thread id (Phase 5).
6. Attach the **Postgres checkpointer**.
7. **Validate** and return structured errors mapped back onto node ids: single reachable entry; every path reaches Output/`END`; no dangling edges; state read-before-write; type compatibility; only intentional cycles; all tool/KB refs resolve.
8. Publish → immutable, hashed **`AgentVersion`**; runs reference `(agent_id, version)`.

## 9. Templates are data, not engine features

A template = `{metadata, category, parameterized GraphSpec, setup_requirements (KBs/creds/params), golden_eval_cases}`.
"Install to canvas" clones the `GraphSpec` and runs a setup wizard. **Zero engine
special-casing** — the five MVP templates (`PLAN.md` §5) are authored `GraphSpec`s over
the registry. Agent-first makes the two RAG templates essentially *one Agent node + a KB
+ a system prompt*; the three multi-agent E-Commerce templates (Phase 5) are a Supervisor
+ worker Agents.

---

## 10. Repo structure & critical files (refines PLAN.md §7)

Same monorepo as `PLAN.md` §7, with **one change for the locked LLM decision**: the
`services/llm-gateway/` box becomes a thin **`services/model/`** client library (a
`ModelClient` protocol + one provider adapter + a stubbed `usage` hook), **not** a full
gateway. The gateway/metering grows here later when we "decide."

```
calypr/
  packages/
    dsl/        # GraphSpec, StateChannel, NodeSpec (Pydantic)  + JSON-Schema→TS codegen  ← the contract
    nodes/      # node registry + MVP node types (Input, Agent, Output, LLM, Retriever, Router, Tool)  ← the heart
    ui/         # shadcn lib + React Flow node/config components (generated config from dsl codegen)
  services/
    compiler/   # DSL → StateGraph + validation                ← the IP
    runtime/    # LangGraph execution, Postgres checkpointer, streaming, HITL resume
    model/      # ModelClient protocol + 1 provider adapter (tool-calling + streaming) + usage hook stub
    ingestion/  # upload/url → chunk → embed → pgvector; exposes retrieve() used by Retriever node AND KB-as-tool
    tools/      # Tool interface + builtin tools + MCP client adapter
  apps/
    web/        # Next.js + React Flow: palette, Agent config, State panel, playground, template gallery
    api/        # FastAPI: Clerk auth, agents CRUD, compile, run/stream (SSE), KB upload
  infra/        # docker, alembic, checkpoint-db, seed
```

**Critical files (create), by the pattern they establish — not an exhaustive list:**

- `packages/dsl/` — `GraphSpec` and the codegen script. *Everything else depends on this; build it first.*
- `packages/nodes/registry.py` + one file per node type — the plugin pattern (§5). Get `input`, `agent`, `output` working before the rest.
- `services/compiler/compile.py` — the `GraphSpec → StateGraph` walk + `validate.py`.
- `services/model/client.py` — `ModelClient` protocol + `anthropic_adapter.py` (tool-calling + streaming).
- `services/tools/` — `Tool` base + `builtin/` + `mcp_client.py`.
- `services/runtime/run.py` — invoke + stream + checkpointer.
- `apps/api/routers/{agents,runs,knowledge}.py` — compile, stream (SSE), upload.
- `apps/web/` — canvas (React Flow), Agent config panel, playground.

## 11. Phased implementation roadmap (start → finish)

We build **phase by phase**, and **do not start a phase until the previous phase's E2E
test passes**. Each phase below lists its backend scope, its front-end deliverable, the
**E2E test that gates it**, and its exit criterion. Phases 0–5 are the MVP; they are a
finer-grained decomposition of `PLAN.md` Phases 0–3, reordered around "Agent node first."
Post-MVP phases are summarized (they map to `PLAN.md` Phases 4–6 and `MVP.md`).

Tooling per layer: **backend** = `pytest` (unit + integration via FastAPI `TestClient`);
**front-end** = component/unit where useful; **E2E** = **Playwright** (available in this
environment) driving the real web app against a running API + Postgres.

---

### Phase 0 — Foundation & scaffolding
*Goal: an authenticated user lands on the app shell; CI is green. No agent logic yet.*

- **Backend / infra:** monorepo (pnpm workspaces + Python via `uv`); `apps/api` FastAPI with `/health`; Postgres + pgvector via `docker-compose`; Alembic baseline migration with `tenant_id` + RLS scaffolding; Clerk JWT verification middleware (org = tenant); `packages/dsl` skeleton + codegen pipeline stub; CI (lint, typecheck, test, **DSL drift check**).
- **Front-end:** `apps/web` Next.js + Tailwind + shadcn + React Flow installed; Clerk sign-in; empty **dashboard** route and an empty **/canvas** route (blank React Flow surface, no nodes yet).
- **E2E test (gate):** Playwright — unauthenticated user is redirected to sign-in; after sign-in lands on the dashboard; `GET /health` returns ok.
- **Exit:** authenticated user sees the dashboard; CI green end-to-end.

### Phase 1 — DSL + node registry + compiler spine *(headless — de-risks the IP first)*
*Goal: a hardcoded `Input → Agent → Output` GraphSpec compiles and runs from a test — proving the compiler before any canvas is built on top of it.*

- **Backend:** `packages/dsl` (`GraphSpec`, `StateChannel`, `NodeSpec`, `EdgeSpec`) + Pydantic→TS codegen + golden fixtures + drift test; `packages/nodes` registry + `Input`, `Agent`, `Output` node types; `services/model` (`ModelClient` protocol + **one** provider adapter with tool-calling + streaming + `usage` stub); `services/compiler` (`GraphSpec → StateGraph` + validation); `services/runtime` (invoke + stream + Postgres checkpointer).
- **Front-end:** none this phase (deliberately headless).
- **E2E test (gate):** `pytest` loads the golden `Input → Agent → Output` fixture → compiles → runs against the model (recorded/mocked for CI, live locally) → asserts a streamed final message. Plus: DSL codegen **drift test** fails on uncommitted regen; invalid-spec fixtures return structured, node-mapped validation errors.
- **Exit:** the riskiest piece (the compiler) runs end-to-end from a script. Everything after is UI on a proven spine.

### Phase 2 — Canvas + playground *(the Agent-first thin slice, full E2E through the UI)*
*Goal: a user builds a basic agent on the canvas and chats with it. This is the MVP proof.*

- **Backend:** `apps/api` — agents CRUD, `POST /compile`, `POST /runs` (SSE streaming), thread/checkpointer wiring.
- **Front-end:** React Flow canvas with a **node palette** (Input / Agent / Output), drag + connect, **Agent config panel** (model, system prompt, max_steps), **State panel** (channels), save → GraphSpec; **Playground** (streaming chat panel showing the step/tool-call trace).
- **E2E test (gate):** Playwright — drag `Input → Agent → Output`, configure the Agent, publish, open the playground, send a message, assert a **streamed** assistant response renders.
- **Exit:** canvas → compile → run → stream works through the real UI. **MVP spine complete.**

### Phase 3 — Tools + RAG *(the Agent becomes genuinely useful)*
*Goal: the agent retrieves from a knowledge base with citations and calls a tool.*

- **Backend:** `services/tools` (`Tool` interface + builtin HTTP + web search + **MCP client adapter**); `services/ingestion` (upload → chunk → embed → pgvector + `retrieve()`); KB-as-tool; `Retriever` node; KB CRUD endpoints.
- **Front-end:** **Knowledge Base** management UI (create KB, upload docs, ingest status); **tool picker** + **KB attach** in the Agent config panel; playground renders **citations** and **tool-call steps**.
- **E2E test (gate):** Playwright — create a KB, upload a doc, build an Agent with that KB + a web-search tool, ask a question; assert the answer **cites the uploaded doc** and the trace shows a **tool call**.
- **Exit:** full single-agent capability — agentic RAG + tools, end to end.

### Phase 4 — Templates + gallery + eval harness
*Goal: a non-expert installs a template, customizes it, and ships a working agent.*

- **Backend:** `packages/templates` — the 2 RAG templates (Customer Service, Document Q&A) as authored `GraphSpec`s + setup requirements + `golden_eval_cases`; install-to-workspace endpoint; `pytest`-runnable eval harness.
- **Front-end:** **template gallery**, **install → canvas**, and a **setup wizard** (fill KB / params / prompt) before first run.
- **E2E test (gate):** Playwright — install Document Q&A from the gallery, complete the setup wizard (upload a doc), chat, assert a cited answer; then run that template's golden eval suite green.
- **Exit:** template → customize → ship, with a passing eval gate per template.

### Phase 5 — Multi-agent (Sub-agent, Supervisor, HITL) + E-Commerce templates
*Goal: a multi-agent team runs end-to-end from the canvas. (Heaviest phase — `PLAN.md` §3.3.)*

- **Backend:** `Sub-agent`, `Supervisor`, `Human-in-the-loop` node types; compiler subgraph composition + supervisor routing/handoffs; `interrupt()` + resume API; sub-agent-as-tool.
- **Front-end:** multi-agent canvas UX (sub-agent nodes, supervisor config + worker wiring); **HITL approval UI** in the playground (pause → approve/edit → resume).
- **E2E test (gate):** Playwright — install the Support team template, ask a question that routes through the supervisor to a worker; assert the multi-agent run completes and a **HITL approval step pauses then resumes**.
- **Exit:** multi-agent topology runs from canvas to playground. **MVP feature-complete.**

---

### Post-MVP (summarized — map to `PLAN.md` 4–6 / `MVP.md`)

- **Phase 6 — Deploy:** per-agent REST API + API keys; embeddable chat widget; scheduled/webhook triggers. *(Chat SDK is the off-the-shelf option for Slack/Teams/Discord here.)*
- **Phase 7 — LLM gateway & monetization:** revisit the deferred "decide later" — provider routing/failover, prompt/result caching, per-tenant token metering → Stripe Meter; cost dashboards + hard caps.
- **Phase 8 — Marketplace & ecosystem:** template marketplace (publish/install/review/revenue-share), connector SDK, MCP server (Calypr agents as tools), per-tenant isolation/SOC2 hardening.

## 12. Testing strategy (applies to every phase)

- **Unit — compiler:** golden `GraphSpec` fixtures → assert expected `StateGraph` structure (nodes, conditional edges, channels); invalid specs → assert structured validation errors mapped to node ids.
- **Unit — DSL contract:** CI regenerates TS from Pydantic and **fails on drift**; golden fixtures validate under both Python and TS.
- **Integration (FastAPI `TestClient`):** `POST /compile` returns a compiled version or structured errors; `POST /runs` streams tokens over SSE; KB upload → `retrieve()` returns cited chunks; the Agent tool loop executes a builtin tool.
- **E2E (Playwright):** the per-phase gate tests above — each runs the real web app against a live API + Postgres and must pass before the next phase starts.
- **Eval seam (from Phase 4):** every template ships `golden_eval_cases` asserting answers contain expected facts; wire LangSmith/LangFuse in a later phase per `PLAN.md`.

## 13. Risks & notes

- **DSL drift** (the kept Python/TS split's tax) — mitigated by the §7 codegen CI gate + golden fixtures. Treat a drift failure as a build break, never a warning.
- **Compiler is the hard part** (`PLAN.md` §10) — the registry pattern (§5) contains the complexity per-node; the Agent subgraph is the only non-trivial compile in the MVP. Budget time there.
- **"Decide later" on the LLM layer** — acceptable, but keep tool-calling + streaming in the `ModelClient` surface from day one (the Agent loop requires them) and keep the `usage` hook stub so metering is a later addition, not a refactor.
- **Sandboxed code execution deferred** — no code-interpreter node in MVP; the Transform node ships only as safe no-code mapping until gVisor/Firecracker sandboxing is in place (`PLAN.md` §3.2 note).
- **MCP-shaped tools now** — costs little, and makes the post-MVP MCP-client workstream nearly free.
