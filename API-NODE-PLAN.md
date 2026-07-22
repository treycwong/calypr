# Calypr — API Node Plan

**Date:** 2026-07-19 · **Status:** PLAN for implementation · **Tracks:**
`CLAUDE-PLAN.md` §6 (unified Tool interface — `source: "builtin" | "connector"`). Naming:
**Phase 8 — API node** (runs after MCP node, Phase 7; reuses its Settings panel).

## 1. What this is

An **API node** that performs `GET` requests to public APIs — Unsplash, Weather, News,
Stocks, … — and writes the result into a state channel an Agent can read with
`{{ state.weather }}`, exactly like a Knowledge node writes retrieved chunks into `context`.

The headline: **API is the `retriever` pattern, not the `tool` pattern.** When a user asks
"will I need an umbrella in Lisbon tomorrow?" or "what's AAPL at?", the agent doesn't need
to *decide* whether to fetch — the fetch is the next deterministic step. So the API node
mirrors `RetrieverNode` (`packages/nodes/src/calypr_nodes/retriever.py`) line-for-line: read
a query from an input channel, fetch, write the formatted result to an output channel.

For the rarer "the LLM should decide when to call" case (e.g. a research agent that searches
the web only if its own knowledge is insufficient), we add a cheap **`http` provider** to the
existing Tool node — same ReAct wiring, no new node. The two modes share one catalog.

**Guiding principles (match the rest of Calypr):**

- **Mirror the Knowledge/RAG seam.** `RetrieverNode` is the 1:1 template. Same shape, same
  integration, same keyless-demo trick (`Open-Meteo` is keyless — the perfect `demo` analog).
- **One catalog, two surfaces.** A single `api_catalog.py` backs both the deterministic
  `api` node and the LLM-decided `tool` provider. Same code paths, same codegen, same
  Settings-panel story.
- **Credentials live in the Settings panel, never in the DSL.** Reuses the vault + UI from
  the MCP plan verbatim.
- **Output is agent-shaped, not raw JSON.** Each catalog provider ships a default Jinja2
  formatter so weather comes out as `"14°C, light rain, in Lisbon"` not 4 KB of JSON.

## 2. Existing contracts to build on (read these first)

| Contract | File | Why it matters |
|---|---|---|
| Knowledge node (`RetrieverConfig`: `source`/`input_channel`/`output_channel`/`channels()`/`compile()`/`codegen()`) | `packages/nodes/src/calypr_nodes/retriever.py` | The exact 1:1 template. `api.py` is `retriever.py` with `httpx.get(...)` swapped for `retriever.ainvoke(...)`. |
| Source catalog (`knowledge_source()` → `KnowledgeSpec`) | `packages/nodes/src/calypr_nodes/knowledge_catalog.py` | The shape `api_catalog.py` copies — `runtime` (None = codegen-only), `code_defs`, `code_ref`, `imports`. |
| Tool catalog (`tool_spec()` → `ToolSpec`) | `packages/nodes/src/calypr_nodes/tools_catalog.py` | Where the `http` provider gets added for the LLM-decided mode (secondary surface). |
| Tool node (`ToolsNode`, `ToolConfig.provider`) | `packages/nodes/src/calypr_nodes/tool.py` | Gains a `"http"` provider value for the secondary surface — same edge-driven binding as `tavily`. |
| Registry plugin pattern | `packages/nodes/src/calypr_nodes/registry.py:75-119` | `@register class ApiNode(BaseNode)` — appears in palette + validate + compile + codegen with no other wiring. |
| Compiler edge-driven tool binding | `services/compiler/src/calypr_compiler/compile.py:62` | Already generic over Tool nodes — `provider: "http"` works the moment it's in the catalog. |
| Templates — fan-out / fan-in pattern | `services/compiler/src/calypr_compiler/templates.py:585` (`trip_planner`) | The Daily Briefing template copies this topology verbatim — multiple API nodes run in parallel, write to their own channels, an orchestrator reads them all. |
| State channels for composition | `services/compiler/src/calypr_compiler/templates.py:13-27` | `_BASE_STATE`, `_RAG_STATE` — add `_API_STATE` with `weather` / `news` / `stocks` / `images`. |
| Settings panel + `/connectors` API | MCP-NODE-PLAN.md §3 Layer 3a + Layer 5 | API keys land here unchanged (Tavily was already heading here; add OpenWeather, Unsplash, NewsAPI, Alpha Vantage, Polygon). |

## 3. Architecture

```
Settings panel (web, sidebar)        ← reused from MCP plan
  └─ API Keys: Unsplash / OpenWeather / NewsAPI / Alpha Vantage / Polygon
                stored envelope-encrypted, RLS-scoped; never in the DSL.

Two surfaces, one catalog:

  (A) api node  ───────────────────────────────────  deterministic, retriever-style
       Input → API(weather) ─┐
                              ├─→ Agent reads {{ state.weather }} → Output
       config: {provider, formatter, output_channel, connector_ref}
       compile: read query from input_channel → httpx.get(...) → format → write to output_channel
       codegen: def node_X(state): query=...; r=httpx.get(...); return {"weather": fmt(r.json())}

  (B) tool node, provider="http"  ─────────────────  LLM-decided, ReAct-style
       Input → Agent ⇄ Tool(http) → Output
       config: {provider: "http", http_url, http_method, http_params, jsonpath}
       compile: ToolNode([BaseTool wrapping httpx])
       codegen: @tool def fetch(...): return httpx.get(...).json()  →  node_X = ToolNode([fetch])

  Both call into api_catalog.py for runtime + codegen.
```

### Layer 1 — Catalog: `api_catalog.py` (new, the heart)

Mirror `knowledge_catalog.py` line-for-line, with a Jinja2 formatter added:

```python
@dataclass
class ApiSpec:
    provider: str                              # "weather_openmeteo", "stocks_alpha", ...
    runtime: Callable[..., Awaitable[str]] | None   # None → codegen-only
    input_template: str                        # "{{ state.messages[-1].content }}" → query string
    output_formatter: str                      # Jinja2 template shaping the JSON → string
    code_defs: list[str]                       # module-level Python (the httpx call + formatter)
    code_ref: str                              # variable name in build_graph()
    imports: list[str]
    requires_key: bool = False                 # if True, lookup connector_ref at compile time
    key_env_name: str = ""                     # e.g. "OPENWEATHER_API_KEY" for codegen .env.example

def api_spec(provider: str, *, connector_ref: str = "", **params) -> ApiSpec: ...
```

The **runtime** is an async fn `(query: str, key: str | None) -> dict` that does the HTTP
call and returns parsed JSON. The **formatter** is applied by the node before writing — each
provider ships a sensible default (weather → `"{{temp}}°C, {{condition}}, in {{location}}"`,
stocks → `"{{symbol}}: ${{price}} ({{change_pct}}% on the day)"`). Users override it in the
config panel.

### Layer 2 — Primary: `api` node (new, mirrors `retriever.py`)

```python
class ApiConfig(BaseModel):
    provider: Literal[
        "weather_openmeteo",   # keyless — the demo analog
        "weather_openweather", # key
        "stocks_alpha",        # key
        "stocks_polygon",      # key
        "news_newsapi",        # key
        "news_gnews",          # key
        "images_unsplash",     # key — writes URLs to context or `images`
        "generic_http",        # user URL + JSONPath
    ] = "weather_openmeteo"
    connector_ref: str = ""               # Settings-panel handle (vault) — empty for keyless
    formatter: str = ""                   # override the catalog default (Jinja2)
    params: dict[str, str] = {}           # static params (units=metric, country=us, ...)
    input_channel: str = "messages"       # where the query comes from (retriever pattern)
    output_channel: str = "weather"       # where the result lands — Agent reads {{ state.<this> }}
    max_length: int = 4000                # truncate to keep state manageable

@register
class ApiNode(BaseNode):
    type = "api"
    meta = NodeMeta(label="API", category="data", icon="cloud",
                    description="Fetch live data from an external API (weather, stocks, news, …).")
    config_model = ApiConfig

    @classmethod
    def reads(cls, cfg):  return [cfg.input_channel]
    @classmethod
    def writes(cls, cfg): return [cfg.output_channel]
    @classmethod
    def channels(cls, cfg):
        return [StateChannel(key=cfg.output_channel, type="string", reducer=Reducer.last)]

    @classmethod
    def compile(cls, cfg, ctx) -> NodeFn:
        spec = api_spec(cfg.provider, connector_ref=cfg.connector_ref, **cfg.params)
        if spec.runtime is None:
            # codegen-only provider — surface a note, mirroring retriever.py:76
            ...
        formatter = cfg.formatter or spec.output_formatter
        async def _run(state):
            query = _query_text(state.get(cfg.input_channel))
            key = _resolve_key(cfg.connector_ref)        # vault lookup; None if keyless
            data = await spec.runtime(query, key)
            text = _render(formatter, data)[:cfg.max_length]
            return {cfg.output_channel: text}
        return _run

    @classmethod
    def codegen(cls, cfg, fn_name, ctx=None) -> CodeFragment:
        # emits a standalone def using httpx + jinja2, reading os.environ[KEY] for the key.
        ...
```

**Three more places to touch (boilerplate):**

- `packages/nodes/src/calypr_nodes/__init__.py` — export `ApiNode`, `ApiConfig` (one line, see `:32`).
- `apps/web/src/lib/graph.ts` — add `"api"` to `CalyprNodeType` (`:7`), `NODE_LABELS` (`:32`), `DEFAULT_CONFIG.api` (`:134`), and an `API_PROVIDER_OPTIONS` constant.
- `apps/web/src/components/canvas/nodes.tsx` — add `ApiNodeView` + register in `nodeTypes` (`:315`). One-line label like RetrieverNode's view (`nodes.tsx:208`).
- `apps/web/src/components/canvas/Palette.tsx` — add `{ type: "api", label: "API", hint: "GET" }` to `ITEMS` (`:6`).
- `apps/web/src/components/canvas/ConfigPanel.tsx` — add an `ApiFields` block (mirrors `RetrieverFields` at `:323`) and dispatch line (`:582`).

### Layer 3 — Secondary: `http` provider on the existing Tool node

For "the LLM should decide when to fetch" (research agents, conditional lookups). Two-line
addition to `tools_catalog.py`:

```python
if provider == "http":
    return ToolSpec(
        provider="http",
        runtime=_http_tool(cfg.http_url, cfg.http_method, cfg.http_params, cfg.jsonpath),
        bind_schema={...},          # name="fetch_<host>", input_schema from http_params
        code_defs=["@tool\ndef fetch_(...): ..."],
        code_ref="fetch_",
        imports=["import httpx", "from langchain_core.tools import tool"],
    )
```

`ToolConfig` gains `http_url`, `http_method`, `http_params`, `jsonpath` fields (ignored unless
`provider == "http"`). No new compiler branch — `_tools_bound_to` (`compile.py:62`) already
walks edges and calls `bind_schemas`. **This is the cheapest possible "agent with API access"
path**, and it's a free by-product of having the catalog.

### Layer 4 — Codegen

Generated module (mirror `retriever.py:97`):

```python
import os
import httpx
from jinja2 import Template

_API_KEY = os.environ["OPENWEATHER_API_KEY"]      # shipped in .env.example, never in source
_fmt = Template("{{temp}}°C, {{condition}}, in {{location}}")

def node_weather(state: State) -> dict:
    """Fetch weather for the latest user message."""
    query = state["messages"][-1].content
    r = httpx.get("https://api.openweathermap.org/data/2.5/weather",
                  params={"q": query, "appid": _API_KEY, "units": "metric"}, timeout=10)
    return {"weather": _fmt.render(r.json())[:4000]}
```

For the `generic_http` provider, codegen emits the user's URL template verbatim with
`{query}` / `{param}` placeholders filled from the config — the no-ceiling escape hatch.

For the Tool-node `http` provider, codegen emits a `@tool`-decorated function the agent
binds (same shape as the `tavily` example at `tools_catalog.py:50`).

### Layer 5 — Settings panel (reused)

The MCP plan's `API Keys` section already anticipated Tavily/OpenAI/Anthropic. This plan
adds: **OpenWeather, Unsplash, NewsAPI, Alpha Vantage, Polygon, GNews.** Zero new UI — just
new entries in the key list. Each is a row: provider name + "Add key" → vault.

Keyless providers (`weather_openmeteo`, `generic_http` without auth) skip the vault entirely
— the canvas + CI stay green with no setup, exactly like `demo_search` and the `demo` KB.

## 4. How it composes with other nodes

Because the `api` node rides the same State-channel contract as `RetrieverNode`, every other
node already knows what to do — **zero changes elsewhere**:

- **Agent / Responder / Revisor** — reads `{{ state.weather }}` / `{{ state.stocks }}` /
  `{{ state.news }}` via the existing template-substitution in the system prompt. The agent
  doesn't know (or care) whether the context came from RAG or an API call.
- **Multiple API nodes** — fan-out like `trip_planner` (`templates.py:585`). Weather, News,
  and Stocks run in parallel, each writing its own channel; an orchestrator reads them all.
- **Router** — branch on whether the user asked about weather vs. stocks vs. news, routing
  to the relevant API node (saves calls). Same conditional-edge mechanism.
- **Evaluator** — score the agent's interpretation of the API data ("did it correctly
  interpret the weather forecast?") like any other.
- **Memory** — store the fetched data across turns so follow-up questions ("and tomorrow?")
  don't re-fetch. Same Memory node, same `memory` channel.
- **Image node** — for `images_unsplash`, the API node can write to the `images` channel an
  Image node reads, composing API + image rendering.
- **Tool node (http provider)** — when the agent should *decide* when to call, swap the
  upstream `api` node for a Tool-node-with-http and the same agent uses it via ReAct.

User-visible effect: drag in `API`, pick a provider (or paste a URL), and any agent
downstream reads the data through `{{ state.X }}`. Identical UX to Knowledge/RAG — that's
the point.

## 5. API providers (the catalog)

Categorised by what works keylessly on the canvas vs. what needs a key in Settings.

### Keyless providers (the `demo` analogs — work on canvas with zero setup)

| Provider | API | Output | Use |
|---|---|---|---|
| **`weather_openmeteo`** | Open-Meteo (no key, no signup) | Temperature, conditions, forecast | **Default in `api` node + the keyless CI/E2E path.** The `demo_search` of API nodes. |
| **`generic_http`** (no auth) | Any public no-auth endpoint (JSONPlaceholder, PokeAPI, REST Countries, Frankfurter FX rates, USGS Quakes, …) | Whatever the user maps via JSONPath | The "build your own" path for any public open API. |

### Key providers (Settings panel → vault)

| Provider | API | Free tier | Use |
|---|---|---|---|
| **`weather_openweather`** | OpenWeatherMap | Yes (60 calls/min) | Most-requested weather API |
| **`images_unsplash`** | Unsplash | Yes (50/hour) | "Show me a picture of X" — writes image URLs |
| **`news_newsapi`** | NewsAPI.org | Yes (100/day, dev only) | Top headlines + search |
| **`news_gnews`** | GNews | Yes (100/day) | NewsAPI alternative, looser license |
| **`stocks_alpha`** | Alpha Vantage | Yes (25/day) | Stocks, forex, crypto |
| **`stocks_polygon`** | Polygon.io | Yes (5/min) | Lower latency, professional tier |

### First-ship recommendation

Ship **`weather_openmeteo`** as the keyless default (so the canvas, tests, CI stay green
just like `demo_search` and the demo KB), plus **`weather_openweather`**, **`images_unsplash`**,
and **`stocks_alpha`** as the three key-backed providers covering the most-requested demos
(weather, image, finance). `news_newsapi` and `generic_http` are the fast-follows.

## 6. Templates

Add to `services/compiler/src/calypr_compiler/templates.py`:

### Framework: `api_passthrough()` — in `FRAMEWORKS`

The minimal hello-world of API nodes (alongside `react()`, `rag()` at `:645`):

```
Input → API(weather_openmeteo) → Agent → Output
```

The agent's system prompt: "Answer the user's weather question using the data in
`{{ state.weather }}`. Be concise." This is the **keyless** API framework — runs on canvas
without any setup, like `simple_reflex()` and `rag()` with the `demo` source.

### Template: `tpl_weather_assistant()` — in `TEMPLATES`

The simple consumer template. Same as the framework template but with OpenWeatherMap (key),
a friendlier system prompt, and a follow-up Router that branches "forecast" vs. "current
conditions" queries to different output formatters. Ships with `setup_requirements` listing
the OpenWeather key scope; setup wizard handles the Settings panel entry.

### Template: `tpl_daily_briefing()` — in `TEMPLATES`  (showcase)

Mirrors `trip_planner`'s fan-out/fan-in topology (`templates.py:585`) — the headline demo:

```
                ┌─→ API(weather_openmeteo) ──┐
Input → Router ─┼─→ API(news_newsapi)       ──┼─→ Synthesizer(Agent) → Output
                └─→ API(stocks_alpha)        ──┘
```

The Router fans out to three API nodes running **in parallel** (LangGraph's `add_messages`
reducer makes concurrent channel writes safe — same trick `trip_planner` uses). Each writes
to its own channel (`weather`, `news`, `stocks`). The synthesizer reads all three via
`{{ state.weather }}` / `{{ state.news }}` / `{{ state.stocks }}` and produces a 3-paragraph
morning briefing. The default keyless config uses `weather_openmeteo` + stub responses for
the key-backed ones, so it runs on canvas out of the box; with keys in Settings, all three
go live.

Both templates go through the existing gallery (`agents.py:80`) and Templates panel
(`TemplatesPanel.tsx`) with **zero** UI changes — the template infrastructure is already
generic over node types and configs.

## 7. Phasing

Each phase ends green (tests + E2E), per the CLAUDE-PLAN discipline.

- **Phase A — Catalog spine + `api` node (headless).** Add `api_catalog.py` with
  `weather_openmeteo` (keyless) + `generic_http`; ship `ApiNode`; unit-test like
  `test_retriever.py`. **Gate:** pytest that compiles `Input → API → Output`, runs against
  Open-Meteo live (or VCR-cassetted for CI), asserts a weather string in `state.weather`.
- **Phase B — Codegen + key providers.** Codegen for all providers; add `weather_openweather`,
  `images_unsplash`, `stocks_alpha`. **Gate:** golden-fixture test asserts the generated
  Python for each provider matches expected output (key from `os.environ[...]`, never inline).
- **Phase C — Canvas UI + Settings keys.** `ApiFields` config panel, `ApiNodeView` renderer,
  Palette entry, Settings-panel API key rows. **Gate:** Playwright — add API node, pick
  `weather_openmeteo`, ask "weather in Lisbon?", assert an answer renders. Then: add
  OpenWeather key in Settings, swap provider, run again.
- **Phase D — Templates.** Ship `api_passthrough()` framework, `tpl_weather_assistant()`,
  `tpl_daily_briefing()`. **Gate:** Playwright — install Daily Briefing template, run with
  `weather_openmeteo` only (keyless), assert a 3-paragraph briefing with the weather live
  and news/stocks showing their stub messages. Then: add NewsAPI + Alpha Vantage keys,
  re-run, assert all three sections live.
- **Phase E — `http` tool provider.** Add the secondary surface on the Tool node for
  LLM-decided fetches. **Gate:** Playwright — Tool node with `provider: "http"`, URL =
  Open-Meteo, agent decides when to fetch, assert a tool-call trace in the playground.

## 8. Risks & open questions

1. **Response size.** APIs (especially News, Stocks) can return large payloads. Mitigation:
   `max_length` truncate (default 4000 chars), plus per-provider sensible formatters that
   drop irrelevant fields before stringifying.
2. **Rate limits.** Users hitting free tiers from Calypr's shared egress IP can blow through
   quotas (Unsplash: 50/hr). Mitigation: per-connector rate limiter in the runtime, surfaced
   as a friendly ToolMessage-style error in the channel ("rate-limited by Unsplash; retry in
   37 minutes") so the agent can explain gracefully.
3. **Schema drift.** An API changes its JSON shape; the formatter breaks. Mitigation:
   formatter errors degrade to `json.dumps(data)[:max_length]` — the agent still gets raw
   data, run doesn't fail. Surfaces a warning event.
4. **Cold-start latency on canvas.** First request to a new provider can be slow (DNS, TLS).
   The existing node `start`/`end` events (`compile.py:46`) cover this; consider a
   per-provider warm-up ping on connector save.
5. **CORS / egress for user-supplied URLs.** `generic_http` calls happen server-side (the
   runtime), so CORS doesn't apply, but egress safety (SSRF) does. Same mitigations as the
   MCP plan §9.1: per-workspace URL allowlist, response size cap, per-connector rate limit.
6. **Image rendering for Unsplash.** v1 writes image URLs as text to `context`; the agent
   describes them. A follow-up writes them to the existing `images` channel so an Image node
   can render inline — composes with the existing Upload + vision-agent path.
7. **Caching.** Weather/stocks don't change second-to-second. A short-TTL response cache
   (per provider, per query) would cut egress cost materially. Decision: ship a 60s
   in-process cache in v1; Redis-backed in a later phase.

## 9. Out of scope (defer)

- **POST/PUT/DELETE methods.** v1 is GET-only (read-only APIs). Write APIs come with a
  separate "Mutation" node + a confirmation/HITL step (Phase 5's HITL pattern).
- **OAuth-flow APIs.** APIs requiring OAuth (not just API keys) defer to the MCP node's
  Tier-A path — those vendors increasingly ship MCP servers anyway.
- **Streaming APIs** (Server-Sent Events, websockets) — defer until a use case demands it.
- **A visual API explorer** (Postman-like request builder in the canvas) — defer; v1 uses
  provider presets + `generic_http` for the long tail.
