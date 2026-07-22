# Calypr — Universal MCP Node Plan

**Date:** 2026-07-19 · **Status:** PLAN for implementation · **Tracks:**
`CLAUDE-PLAN.md` §6 (unified Tool interface), §Phase 3 (`services/tools/mcp_client.py`),
`MVP.md` "MCP client support." Naming: **Phase 7 — MCP node** (runs after RAG ingestion,
Phase 6).

## 1. What this is

A **Universal MCP node** on the canvas: pick any [Model Context Protocol](https://modelcontextprotocol.io)
server — Notion, Google Drive, GitHub, … — and its tools become available to any connected
Agent/Responder/Revisor through the same ReAct loop as today's `demo_search` / `tavily` tools.

The headline: **MCP is a new value in an existing dropdown, not a new system.** Almost all
the work is in `tools_catalog.py`, `ToolConfig`, a new **Settings panel** for credentials,
and one new template. Every other node already speaks the Tool-node contract.

**Guiding principles (match the rest of Calypr):**

- **Reuse the Tool seam.** An MCP server is just a list of `{name, description, input_schema}`
  — exactly the existing `bind_schema`. No new node type, no new edge type, no new compiler
  branch beyond a single `isinstance` flatten.
- **Mirror the Knowledge/RAG three-tier shape.** `demo` (keyless, runs on canvas) → curated
  connector (OAuth, runs on canvas) → codegen-only (user's own infra). Same model users
  already know from `RetrieverNode`.
- **Credentials live in a Settings panel, never in the DSL.** The canvas stores a
  `connector_ref`; the secret lives in the per-workspace vault (anticipated in
  `CLAUDE-PLAN.md:190`: `auth: CredentialRef | None`). This is the **most protected** path
  (see §5 — Tier A).
- **Tiered onboarding.** Normal users click "Connect Notion"; builders paste a URL; devs
  edit `mcp.json` locally. Each tier has a working path on day one.

## 2. Existing contracts to build on (read these first)

| Contract | File | Why it matters |
|---|---|---|
| Tool node (`ToolsNode`, `ToolConfig`: `provider`/`api_key`/`max_results`) | `packages/nodes/src/calypr_nodes/tool.py` | The node we extend. `bind_schemas()` and `code_refs()` are how it advertises tools to a connected LLM; `compile()` and `codegen()` are the two altitudes. |
| Source catalog (`tool_spec()` → `ToolSpec`) | `packages/nodes/src/calypr_nodes/tools_catalog.py` | Where `mcp` gains a runtime tool list + ownable codegen. The proven pattern (`tavily` is codegen-only; `demo_search` is runtime). |
| Knowledge mirror (`knowledge_catalog.py` + `retriever.py`) | `packages/nodes/src/calypr_nodes/` | The exact three-tier shape (`demo` / `pgvector`) to copy for MCP (`demo` / curated / custom URL / stdio). |
| Edge-driven tool binding (`_tools_bound_to`) | `services/compiler/src/calypr_compiler/compile.py:62` | Walks edges and calls `tool_cls.bind_schemas(cfg)` — never asks *what kind* of tool. One flatten for list-returning catalogs. |
| Edge-driven codegen (`_tool_refs`) | `services/codegen/src/calypr_codegen/generate.py:147` | Mirrors the compiler for the "code" altitude. Plus the `tools_condition` ReAct wiring at `:213`. |
| Canvas renderer (`ToolNodeView`) | `apps/web/src/components/canvas/nodes.tsx:194` | Already shows `config.provider`. No changes for a new provider. |
| Config panel (`ToolFields`) + dropdown source | `apps/web/src/components/canvas/ConfigPanel.tsx:290`, `apps/web/src/lib/graph.ts:51` | Where MCP-specific fields render; where `TOOL_PROVIDER_OPTIONS` gains the `mcp` entry. |
| Sidebar icon rail (Palette / Templates / …) | `apps/web/src/app/canvas/page.tsx:582` | Where the new **Settings** tab lives. |
| Tenant CRUD pattern (`Depends(tenant)`, RLS) | `apps/api/src/calypr_api/routers/agents.py` | Copy for `/connectors`. |
| Engine context injection (`context_for(graph)`) | `apps/api/src/calypr_api/engine.py` | Where vault-resolved MCP credentials are injected at compile time, mirroring how KB retrievers will be. |
| ToolNode (LangGraph) | `langgraph.prebuilt.ToolNode` | Already accepts a list of `BaseTool`s — MCP tools fit in unchanged. |

## 3. Architecture

```
Settings panel (web, sidebar)
  └─ Connected Accounts: "Connect Notion" → OAuth → token to vault (workspace-scoped, RLS)
  └─ MCP Servers: paste URL → "Test" → ListTools → save with a connector_ref
  └─ API Keys: Tavily / OpenAI / … (migrated from per-node fields)

Canvas
  Tools node → ConfigPanel "Provider: MCP"
                ├─ Connector dropdown (from /connectors)         ← Tier A (curated)
                ├─ OR: URL + transport fields                     ← Tier B (custom HTTP)
                └─ OR: stdio command (codegen-only badge)         ← Tier C (local)

  ToolConfig stores only `mcp_connector_ref` (a vault handle) — never the secret.

Compiler (compile.py)
  For each Tools node with provider=mcp:
    resolve connector_ref → vault → live MCP client (cached per workspace+server)
    ListTools() → [BaseTool...] → bind to upstream LLM via the existing edge walk.

Codegen (generate.py)
  Emits MultiServerMCPClient({...}) reading os.environ["MCP_URL"] / ["MCP_TOKEN"] —
  secrets never serialized. Ships a .env.example with the template.

Runtime (run.py)
  Unchanged — ToolNode over the remote tools; ToolMessages flow into `messages` like any
  other tool call.
```

### Layer 1 — Catalog: `tools_catalog.py` (the heart)

Add an `mcp` branch to `tool_spec()`. Library: **`langchain-mcp-adapters`**
(`MultiServerMCPClient`) — official-ish, returns LangChain `BaseTool`s, supports all three
transports (stdio / SSE / streamable-http). Same library LangGraph docs recommend.

```python
tool_spec("mcp", server={"url": "...", "transport": "streamable_http"}, token=...)
  → connects (lazy, cached per workspace+url), calls ListTools()
  → wraps each remote tool as a BaseTool
  → runtime = ToolNode([*remote_tools])
  → bind_schema = [remote_tool_schemas...]   # list — see Layer 2
  → code_defs = "mcp = MultiServerMCPClient({...}); tools = asyncio.run(mcp.load_tools())"
  → code_ref = "*tools"
```

**One breaking-shape change:** `ToolSpec.bind_schema` is currently a single `dict`; an MCP
server yields N. Make it `dict | list[dict]` and add a one-line flatten in
`compile.py:71-74` and `generate.py:155-157`. Future-proofs every provider for multi-tool
servers.

### Layer 2 — Node config: `tool.py`

`ToolConfig` gains MCP-specific fields behind a discriminated branch:

```python
class ToolConfig(BaseModel):
    provider: Literal["demo_search", "tavily", "mcp"] = "demo_search"
    api_key: str = ""                 # existing — DEPRECATED for new providers (see Settings)
    max_results: int = 3              # existing
    # MCP-only (ignored unless provider == "mcp"):
    mcp_connector_ref: str = ""       # vault handle from the Settings panel (Tier A or B)
    mcp_transport: Literal["http", "sse", "stdio"] = "http"
    mcp_url: str = ""                 # Tier B only — saved as a connector via Settings
    mcp_command: list[str] = []       # Tier C only — codegen-only
    mcp_env_keys: list[str] = []      # Tier C only — env var NAMES (never values)
    mcp_tool_filter: list[str] = []   # subset of server's tools to bind (empty = all)
```

`bind_schemas`, `code_refs`, `compile`, `codegen` each grow an `if cfg.provider == "mcp"`
branch that delegates to `tool_spec("mcp", …)`. **All other node code is unchanged.**

The secret never appears in `ToolConfig`. Only `mcp_connector_ref` does — a vault handle.
At compile time, `engine.context_for(graph)` resolves it server-side.

### Layer 3 — Canvas UI

#### 3a. New sidebar tab: **Settings**

Added to the icon rail in `apps/web/src/app/canvas/page.tsx:582` alongside Palette and
Templates. Three sections:

| Section | Purpose | Backing endpoint |
|---|---|---|
| **Connected Accounts** | Tier A — OAuth'd apps (Notion, Google Drive, …). Shows status (`Connected as @x` / `Reconnect` / `Disconnect`). | `GET /connectors?tier=a`, `POST /connectors/{id}/connect`, `DELETE /connectors/{id}` |
| **MCP Servers** | Tier B — user-added URLs. "Add server" form (URL, transport, optional bearer). "Test" button → shows discovered tools. | `GET /connectors?tier=b`, `POST /connectors` (validates via `/mcp/discover`), `POST /connectors/{id}/test` |
| **API Keys** | Existing providers migrated out of per-node config — Tavily, OpenAI, Anthropic. Today these live awkwardly on the Tool node; this is the cleanup. | `GET /api-keys`, `PUT /api-keys/{provider}` |

The Settings panel **becomes the only place secrets are entered**. The Tool node's config
panel references them by dropdown (`Connector: [Notion · @user]` or `Server: [my-custom]`).

#### 3b. Config panel changes (`ConfigPanel.tsx:290`)

When `provider === "mcp"`:
- **Connector dropdown** (Tier A + B entries from `/connectors`) — primary path.
- **Advanced:** transport selector, raw URL, command (Tier C, codegen-only badge).
- **Tool filter** multi-select — populated by hitting `/mcp/discover` after a connector is
  picked. Empty = bind all (default).
- A small "Test connection" button next to the dropdown → calls `/connectors/{id}/test` and
  surfaces errors inline.

`DEFAULT_CONFIG.tool` in `graph.ts:180` gains the new fields with empty defaults.

#### 3c. Canvas renderer (`nodes.tsx:194`)

Unchanged structurally. Optionally show the connector host next to the `mcp` provider tag
(`ToolNodeView` reads `config.mcp_connector_ref` → display label).

### Layer 4 — Codegen

Generated module (mirrors the existing `tavily` pattern at `tools_catalog.py:50`):

```python
from langchain_mcp_adapters import MultiServerMCPClient

mcp = MultiServerMCPClient({
    "custom": {
        "url": os.environ["MCP_URL"],
        "transport": "streamable_http",
        "headers": {"Authorization": f"Bearer {os.environ['MCP_TOKEN']}"},
    }
})
mcp_tools = asyncio.run(mcp.load_tools())
node_X = ToolNode(mcp_tools)
```

OAuth tokens / API keys **never** appear in generated source — they read from
`os.environ[...]`, matching the existing `api_key` "runtime-only" rule (`tool.py:31`). The
template ships a `.env.example` listing every var.

For **stdio** transport: codegen-only (Calypr's servers can't spawn a process on the user's
laptop). Generated module spawns the configured command — same `codegen-only` escape hatch
as `pgvector` (`knowledge_catalog.py:44`).

### Layer 5 — API surface (new `routers/connectors.py`)

| Endpoint | Purpose |
|---|---|
| `GET /connectors?tier=a\|b` | List the workspace's connected accounts + MCP servers. |
| `POST /connectors` | Tier B — save a `{name, url, transport, bearer?}`. Validates via `/mcp/discover`. |
| `POST /connectors/{id}/connect` | Tier A — start OAuth (returns redirect URL). |
| `GET /connectors/{id}/callback` | OAuth callback; stores token in the vault. |
| `POST /connectors/{id}/test` | Calls `ListTools`; returns tool list (drives the canvas Test button). |
| `DELETE /connectors/{id}` | Revokes + removes. |
| `GET /api-keys` / `PUT /api-keys/{provider}` | Existing providers migrated here. |

`Depends(tenant)` scoping + RLS — copy the `agents.py` pattern. Tokens stored in a new
`connector_credential` table (envelope-encrypted), never returned to the client.

## 4. How it interacts with other nodes seamlessly

Because MCP rides the existing Tool-node contract, every other node already knows what to
do — no other node changes:

- **Agent / Responder / Revisor** — wired to an MCP Tool node, the compiler
  (`compile.py:62-79`) auto-binds all the server's tool schemas to that LLM. The LLM calls
  any of them; the Tool node executes; the canonical ReAct loop (already wired in
  `generate.py:213-228` via `tools_condition`) routes back.
- **Router** — branches on whether the user's request needs an external action, routing to
  the Agent-with-MCP branch vs. a pure-LLM branch. Same conditional-edge mechanism.
- **Evaluator** — scores the agent's MCP-grounded answer like any other.
- **Memory** — ToolMessages from MCP calls land in the same `messages` channel and get
  buffered/summarized identically.
- **Knowledge (RAG)** — composes naturally. An agent can retrieve from a pgvector KB *and*
  call Notion: two tools, both bound by the same edge walk.
- **Code node** — power user's escape hatch remains intact; they can call the bound MCP
  tools directly.

User-visible effect: drag in `Tools`, switch provider to `MCP`, pick a connector — and any
agent upstream instantly has those tools. Same ReAct topology as `react()` in `templates.py`,
just with a different tool source.

## 5. Tiering, security, and the Settings panel

**Three tiers, easiest → hardest. Tier A is the most protected and the default for normal
users.**

| Tier | Who | Setup | Where it runs | Security posture |
|---|---|---|---|---|
| **A — Curated OAuth connector** | Normal user | Click "Connect Notion" in Settings → OAuth in browser → done | Calypr-hosted proxy (runtime + codegen) | **Highest.** Calypr controls the OAuth flow, the scopes (pre-approved, minimal), the token storage (envelope-encrypted vault + RLS), the token rotation/revocation, and the egress (only vetted, allowlisted MCP servers). The user never sees a token; the DSL never carries one. |
| **B — Public HTTP MCP server** | Builder | Paste URL in Settings → "Test" → pick tools | Calypr-hosted (runtime + codegen) | Medium. URL is user-supplied (SSRF / malicious-tool surface). Mitigations: per-workspace allowlist toggle, per-connector rate limits, optional egress allowlist, sandboxed HTTP client. |
| **C — Local stdio MCP server** | Dev | Edit `mcp.json` locally; env var names in canvas | Codegen-only (their machine) | User-managed. Calypr never sees the server; only emits code that spawns it. |

### Why Tier A is the most secure path

The Settings panel is the architectural enforcement point:

1. **The user never types a secret into the canvas.** The Tool node stores a
   `mcp_connector_ref` (a vault handle), not a token. Even if a graph spec leaks, the
   attacker gets a handle, not a credential.
2. **OAuth scopes are pre-approved per connector.** A user can't escalate — Notion is
   scoped to `pages:read` if that's all Calypr requests; there's no UI to widen it.
3. **Tokens are envelope-encrypted at rest, RLS-scoped to the workspace.** Same pattern as
   the upcoming `agent_versions` and KB tables. No cross-tenant leakage.
4. **Egress is bounded.** Tier A connectors only ever call the vendor's official MCP server
   (e.g. `https://mcp.notion.com/mcp`) — Calypr's HTTP allowlist blocks anything else. SSRF
   is impossible because the URL isn't user-controlled.
5. **Revocation is one click.** "Disconnect" in Settings revokes the OAuth token + deletes
   the vault row; every graph referencing that `connector_ref` fails closed with a clear
   error on next run.
6. **Audit trail.** Every connector use is logged per-run in `metering` (already wired),
   so admins see "Agent X called Notion tool `search` 12 times."

Tier B and C inherit (1) and (5) but not (2)/(3)/(4) — which is why Tier A is the
recommended default and the one marketing should demo.

### Settings panel — what migrates

Two existing per-node secret fields migrate into Settings for the same protection:

- `ToolConfig.api_key` (Tavily today) → `API Keys` section. The Tool node picks "Tavily ·
  [key on file]" instead of typing a key.
- Future codegen-only providers (OpenAI, Anthropic, embedding keys) land here too.

Old fields stay accepted for backward-compat with saved specs; new ones are written through
the Settings panel.

## 6. MCP-ready apps to test against

Categorised by what works on Calypr today (HTTP transport = hosted; stdio = codegen-only).

### Tier A candidates — curated OAuth connectors (hosted, official MCP servers)

These ship their own cloud-hosted MCP server with OAuth, so Calypr can proxy them safely.

| App | Server | Scopes Calypr should request | Ship in phase |
|---|---|---|---|
| **Notion** | `https://mcp.notion.com/mcp` (official) | `pages:read`, `pages:write` (optional) | **D** (first) — top-3 requested integration; most mature MCP server |
| **Google Drive** | official Google MCP adapter | `drive.metadata.readonly`, `drive.file.readonly` | D+1 — covers the "read my docs" use case |
| **GitHub** | `https://api.githubcopilot.com/mcp/` (official) | `repo:read`, `issues:read` | D+2 — devs want this for codebase Q&A |
| **Linear** | official Linear MCP server | `read` | D+3 — fast-growing PM use case |
| **Slack** | official Slack MCP server (preview) | `channels:read`, `channels:history` | D+4 — universal "what did my team say" |
| **Atlassian (Jira/Confluence)** | official Atlassian MCP server | `read:jira-work`, `read:confluence` | D+5 — enterprise pull |
| **Stripe** | official Stripe MCP server (limited) | `read_only` | later — finance use case |

### Tier B candidates — public HTTP MCP servers (test without OAuth)

For builder demos and the keyless E2E test path:

| Server | Use | Notes |
|---|---|---|
| **`@modelcontextprotocol/server-everything`** (HTTP mode) | Reference test server — has every tool/resource/prompt type | **Use this in CI** and as the default in the `mcp_react()` framework (the analog of `demo_search`). |
| **Browserbase** (hosted MCP) | Headless browser tool | Good demo for "agent browses the web." |
| **Firecrawl** (hosted MCP) | Web crawl/extract | Useful for research agents. |
| **Postgres MCP** (hosted variants exist) | Read-only SQL | Useful for "chat to my database" agents. |

### Tier C candidates — local stdio servers (codegen-only, the dev escape hatch)

Document these in the template's `setup_requirements`; users run them in their generated
agent against their own data:

| Server | Use |
|---|---|
| **`@modelcontextprotocol/server-filesystem`** | Local files (the "chat to my repo" pattern) |
| **`@modelcontextprotocol/server-sqlite`** | Local sqlite DB |
| **`@modelcontextprotocol/server-time`** | Current time / timezone |
| **`@modelcontextprotocol/server-fetch`** | HTTP fetch (no scraping) |
| **`@modelcontextprotocol/server-memory`** | Local knowledge graph |
| **`@modelcontextprotocol/server-sequential-thinking`** | Chain-of-thought tool (good for demos) |

### First-ship recommendation

Ship **Notion** as the inaugural Tier-A connector (most mature, top-requested, best demo),
plus **`server-everything`** as the keyless Tier-B test target. That gives you a real-user
demo (Notion) and a deterministic CI path (everything server) on day one. Google Drive and
GitHub are the fast-follows.

## 7. Templates

Add to `services/compiler/src/calypr_compiler/templates.py`:

### Framework: `mcp_react()` — in `FRAMEWORKS` (alongside `react()`, line 652)

A copy of `react()` with the Tool node configured for
`provider: "mcp", mcp_connector_ref: "demo-everything"`. Calypr hosts a sandbox
`server-everything` instance — the MCP analog of `demo_search`. This keeps the framework
keyless + deterministic like the rest of the gallery, so the existing E2E test pattern
(`e2e/tests/phase5.spec.ts`) ports directly.

### Template: `tpl_notion_assistant()` — in `TEMPLATES` (alongside `trip_planner()`, line 663)

```
Input → Agent(orchestrator) ⇄ Tool(MCP/Notion connector) → Output
```

System prompt: "You answer questions from the user's Notion. Use the search tool to find
relevant pages, then answer with citations." Ships with `setup_requirements` listing the
Notion OAuth scope; the setup wizard (CLAUDE-PLAN §Phase 4) handles the Connect button.

### Template: `tpl_workspace_search()` — fast-follow

Composes Notion + Google Drive + a pgvector KB in one orchestrator — the "search my whole
workspace" demo. Showcases MCP + RAG composing through the same Tool-node seam.

Both go through the existing gallery (`agents.py:80`) and Templates panel
(`TemplatesPanel.tsx`) with **zero** UI changes — the template infrastructure is already
generic over node types and configs.

## 8. Phasing

Each phase ends green (tests + E2E), per the CLAUDE-PLAN discipline.

- **Phase A — Catalog spine (headless).** Add `tool_spec("mcp", …)` for HTTP transport;
  extend `bind_schema` to allow lists; unit-test against `server-everything` running in CI.
  Codegen-only path ships first (no runtime risk). **Gate:** pytest that loads an MCP-served
  `ToolSpec` and compiles; golden fixture for the generated Python.
- **Phase B — Runtime execution.** Add `langchain-mcp-adapters` runtime branch; `ToolNode`
  over remote tools. **Gate:** pytest that calls `server-everything` in a real graph.
- **Phase C — Settings panel + Tier B.** New sidebar tab, `/connectors` CRUD, `/mcp/discover`,
  canvas MCP fields + Test button. **Gate:** Playwright — add MCP Tools node, save a
  connector in Settings, paste `server-everything` URL, see discovered tools, run agent,
  assert a tool-call trace.
- **Phase D — Notion (Tier A) + template.** OAuth flow, vault storage, `mcp_react()`
  framework, `tpl_notion_assistant()` template. **Gate:** Playwright — install template,
  OAuth in Settings, ask a question, assert a Notion-grounded answer with citations.
- **Phase E — Migrate existing keys.** Move `ToolConfig.api_key` to the Settings API Keys
  section. Backward-compat shim reads old fields. **Gate:** existing Tavily tests still
  pass; new tests assert the migrated path.

## 9. Risks & open questions

1. **Calypr-as-proxy security (Tier B).** User-supplied URLs are SSRF / malicious-tool
   surface. Mitigation: per-workspace URL allowlist toggle, egress allowlist on the runtime
   HTTP client, per-connector rate limits, response size cap. **Decision needed:** default
   open + warn, or default allowlist-only.
2. **Tool-list dynamism.** An MCP server's tool list can change between design-time (canvas)
   and run-time. **Recommend** binding to the snapshot taken at "Test" time (stored in the
   connector row); validation flags drift on next run.
3. **Streaming UX.** MCP servers can be slow (seconds per call). The node already emits
   `start`/`end` events (`compile.py:46`); add a per-tool-call progress event for
   long-running tools.
4. **Library lock-in.** `langchain-mcp-adapters` is pre-1.0. Mitigation: isolate it inside
   `tool_spec("mcp", …)` — one file to swap if we change libraries.
5. **Cost.** Curated OAuth connectors (Tier A) make Calypr the egress payer. **Decision:**
   free tier with rate limit, paid tier for unlimited, or BYO-key only? Aligns with
   `PRICING-SPEC.md`.
6. **Token rotation.** OAuth refresh tokens expire. The Settings panel needs a background
   refresh job + a "Reconnect" badge when refresh fails. Standard OAuth hygiene.
7. **OAuth app provisioning.** Each Tier-A connector needs a Calypr-registered OAuth app
   per vendor. One-time setup per connector; document in `infra/`.

## 10. Out of scope (defer)

- **Calypr as MCP server** (Calypr agents exposed as tools) — `MVP.md` G4 / CLAUDE-PLAN
  Phase 8. Separate workstream; doesn't block this plan.
- **Marketplace for MCP connectors.** Community-contributed connector entries in the
  Settings panel — Phase 8.
- **Per-tool billing surcharges** for premium connectors — revisit with pricing.
- **Streaming MCP resources/prompts** — Phase 1 supports tools only (the LangChain adapter
  surface). Resources/prompts land when `langchain-mcp-adapters` stabilizes that API.
