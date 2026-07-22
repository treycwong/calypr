# Calypr — AI Assistant Feature Spec (v1: "prompt → canvas")

**Date:** 2026-07-02 · **Status:** SPEC for implementation (hand to a coding agent as-is)
· **Effort:** ~1 week solo · **Depends on:** nothing unshipped (usage *persistence* is
optional, see §8)

## 1. What this is

Wire up the currently-disabled AI assistant panel
(`apps/web/src/components/canvas/AssistantPanel.tsx` — a scaffold rendering "coming soon")
so a user can type:

> "I would like a RAG chatbot for my website."

…and the canvas refreshes with an intelligently wired graph (e.g. Input → Retriever →
Agent → Output) expressed in the existing GraphSpec DSL, which already compiles to
LangGraph and generates ownable Python. The assistant does **not** invent a new runtime
path — it emits a `GraphSpec`, and everything downstream (compile, run, codegen) already
exists.

**Decided scope (v1):**
- **Generate + refine.** First prompt produces a full graph. Follow-up messages ("now add
  a translation step") regenerate the **whole graph** using the conversation history and
  the current spec as context. No surgical node-level editing engine (that's the Month-4
  copilot).
- **Auto-apply + undo.** The canvas refreshes the moment a graph arrives. A "Restore
  previous" chip in the chat reverts to the pre-apply graph (one level of undo is enough
  for v1).
- **Models:** Kimi (Moonshot), OpenAI, DeepSeek — all through the existing `ModelClient`
  seam (§4). Default configurable by env; keyless `fake` path preserved for CI/e2e.

## 2. Existing contracts to build on (read these first)

| Contract | File | Why it matters |
|---|---|---|
| `GraphSpec` / `NodeSpec` / `EdgeSpec` / `StateChannel` | `packages/dsl/src/calypr_dsl/spec.py` | The assistant's entire output is one `GraphSpec`. TS types are generated from it (drift check in CI). |
| `validate_graph(graph) -> issues` | `services/compiler` (used in `apps/api/src/calypr_api/routers/agents.py::compile_spec`) | The judge in the repair loop (§5). |
| Node registry (12 types + config models) | `packages/nodes/src/calypr_nodes/` | Source of the node catalog in the system prompt — generate it, don't hand-write it. |
| `FRAMEWORKS` / `TEMPLATES` | `services/compiler/.../templates.py` | Few-shot examples: real, valid GraphSpecs. |
| `ModelClient` protocol + `model_for()` | `services/model/src/calypr_model/{base,factory}.py` | Extend for Kimi/DeepSeek (§4). `OpenAIModelClient` already streams + accumulates tool calls. |
| SSE streaming pattern | `apps/api/src/calypr_api/routers/runs.py` + web proxy `apps/web/src/app/api/runs/route.ts` + reader `apps/web/src/lib/api.ts::runAgent()` | Copy this pattern exactly for `/assist`. |
| Template → canvas load path | `apps/web/src/components/canvas/TemplatesPanel.tsx` | The assistant applies graphs to the canvas through the same conversion/layout path templates use. |
| Tenant scoping | `apps/api/src/calypr_api/deps.py::tenant` | `/assist` must take the `tenant` dep like every data route. |

## 3. Architecture

```
AssistantPanel.tsx ──POST /api/assist (SSE proxy)──▶ apps/web/src/app/api/assist/route.ts
                                                        │  (same proxy pattern as /api/runs)
                                                        ▼
                          apps/api routers/assist.py  POST /assist   [tenant-scoped]
                                                        │
                                                        ▼
                          services/assistant (new pkg: calypr_assistant)
                            build prompt ─▶ model_for(ASSISTANT_MODEL) ─▶ parse JSON
                                 ▲                                          │
                                 └────────── repair loop (≤2) ◀── validate_graph
                                                        │
                                              SSE: status / note / graph / usage / error
```

**New package** `services/assistant/src/calypr_assistant/` (mirror the layout of
`services/codegen`). Deps: `calypr_dsl`, `calypr_model`, `calypr_compiler`,
`calypr_nodes`. No web/API imports — keep it a pure library like the other services.

## 4. Model routing (Kimi / OpenAI / DeepSeek)

Kimi (Moonshot) and DeepSeek both expose **OpenAI-compatible** Chat Completions APIs, so
no new client class is needed — parametrize the existing one:

1. `OpenAIModelClient.__init__(base_url: str | None = None, api_key: str | None = None)`
   → pass through to `AsyncOpenAI(...)`. Default behavior unchanged.
2. Extend `provider_of()` / `model_for()` in `services/model/src/calypr_model/factory.py`:

   | model id prefix | provider | client | env key |
   |---|---|---|---|
   | `fake` | fake | `FakeModelClient` | — |
   | `claude*`, `anthropic*` | anthropic | `AnthropicModelClient` | `ANTHROPIC_API_KEY` |
   | `kimi*`, `moonshot*` | moonshot | `OpenAIModelClient(base_url=MOONSHOT_BASE_URL)` | `MOONSHOT_API_KEY` |
   | `deepseek*` | deepseek | `OpenAIModelClient(base_url=DEEPSEEK_BASE_URL)` | `DEEPSEEK_API_KEY` |
   | everything else | openai | `OpenAIModelClient()` | `OPENAI_API_KEY` |

3. Config: `CALYPR_ASSISTANT_MODEL` env var (e.g. `kimi-k2`, `deepseek-chat`,
   `gpt-4.1-mini`). **Unset ⇒ `fake`** so dev/CI stay keyless (§9).

> ⚠️ **Builder note:** do NOT trust training data for Moonshot/DeepSeek base URLs, model
> ids, or JSON-mode support — verify against their current API docs at build time and put
> the base URLs in env/settings, not hardcoded. Same for whether each supports
> `response_format={"type":"json_object"}`; if a provider doesn't, rely on the prompt
> contract + the repair loop instead. Because these agent nodes will also carry
> `kimi-*`/`deepseek-*` model ids at *runtime*, this factory change benefits normal runs
> too — add a live-test marker like the existing optional OpenAI live test.

## 5. Generation pipeline (`calypr_assistant`)

`async def draft_graph(messages, current_graph, model_id) -> AsyncIterator[AssistEvent]`

1. **System prompt** (build once at import, cached):
   - The GraphSpec **JSON schema** via `GraphSpec.model_json_schema()` (never hand-write it;
     `schema_version` currently `0.1.0`).
   - A **node catalog** generated from the registry: for each of the 12 node types, its id,
     one-line description, and config field schema. Derive from `calypr_nodes` metadata so
     new node types are picked up automatically.
   - **2–3 few-shot pairs**: a plausible user request + the serialized spec of a real
     template (`model_dump()` of e.g. the RAG framework, a Router template, and the
     Orchestrator–Worker template). These teach wiring conventions (entry node, `messages`
     channel with `append` reducer, router `condition` edges, retriever→agent grounding).
   - **Hard rules:** output exactly one JSON object (no prose, no fences); every edge
     endpoint must reference a declared node id; exactly one `input` node as `entry`;
     ≥1 `output` node; **the `code` (Custom Code) node type is forbidden in v1** (never
     auto-place generated Python on a user's canvas — quality + injection surface);
     omit `position` (layout is applied client-side, §7).
2. **User turn assembly:** conversation history verbatim; if `current_graph` is present
   (refine mode), append it as JSON with the instruction "produce the FULL updated graph,
   not a diff."
3. **Call the model** via `ModelClient.stream()` — accumulate `TextDelta`s; use JSON mode
   where the provider supports it. Cap `max_tokens` (~4k) — a GraphSpec is small.
4. **Parse:** strip stray fences defensively → `GraphSpec.model_validate_json`. Normalize:
   assign fresh `id` (uuid), keep the model's `name`/`description`, dedupe node ids.
5. **Validate:** `validate_graph()`. On errors → **repair loop**: re-prompt with the issue
   list ("fix these and return the full corrected JSON"), max **2 retries**. Still failing
   → emit `error` with the issues (the panel renders them; the canvas is untouched).
6. **Emit events** (§6) throughout; include token `usage` from the model client.

## 6. API + SSE event protocol

`POST /assist` in new `apps/api/src/calypr_api/routers/assist.py` (register in `main.py`;
add `AssistRequest` to `schemas.py`):

```jsonc
// request
{ "messages": [{"role": "user|assistant", "content": "..."}],
  "current_graph": { /* GraphSpec */ } | null,
  "model": "kimi-k2" /* optional; default = settings.assistant_model */ }
```

SSE stream (same envelope/termination style as `/runs`, ending with `[DONE]`):

| event | payload | purpose |
|---|---|---|
| `status` | `{"phase": "drafting" \| "validating" \| "repairing"}` | progress line in the panel |
| `note` | `{"text": "..."}` | one short sentence the assistant says about what it built (generated as a tiny second call with the cheap model, or a static summary of node counts — builder's choice; keep it cheap) |
| `graph` | `{"spec": {...GraphSpec}}` | the deliverable; at most one per request |
| `usage` | `{"input_tokens": n, "output_tokens": n, "model": "..."}` | cost visibility |
| `error` | `{"message": "...", "issues": [...]}` | validation failure after retries, provider error |

Web proxy: `apps/web/src/app/api/assist/route.ts`, copying the `/api/runs` SSE
pipe-through (auth headers via `lib/api-headers.ts`).

## 7. Frontend (`AssistantPanel.tsx` + canvas wiring)

- Replace the scaffold: message list (user/assistant bubbles), input + Send enabled,
  streaming status line. Keep the existing `data-testid`s (`assistant-panel`,
  `assistant-input`) — e2e depends on them; add `assistant-send`, `assistant-restore`.
- Add `assistAgent()` beside `runAgent()` in `apps/web/src/lib/api.ts` (generalize the
  SSE reader rather than duplicating it, if trivial).
- On `graph` event:
  1. Snapshot current React Flow nodes/edges (single-level undo).
  2. Convert spec → canvas through the **same code path `TemplatesPanel.tsx` uses**
     (spec→flow conversion + the existing left-to-right layered auto-layout — locate it in
     `apps/web/src/lib/graph.ts`; do not write a second layout).
  3. Clear selection, mark the graph unsaved (same semantics as loading a template:
     `agentId = null` so next Save creates a new agent — unless refining an already-open
     agent, in which case keep `agentId` and let Save update it).
  4. Render a "Restore previous" chip on that assistant message; clicking swaps the
     snapshot back (chip then flips to "Re-apply").
- Refine mode: every request sends the **current canvas spec** as `current_graph` (the
  canvas is the source of truth, so hand-edits between prompts are respected).
- The disabled state remains when the backend reports the assistant is unavailable
  (surface a friendly note instead of "coming soon").
- Analytics (PostHog, once wired per MVP plan Week 1): `assistant_prompted`,
  `assistant_graph_applied` (node/edge counts, model), `assistant_restore`,
  `assistant_error`.

> ⚠️ **Builder note:** `apps/web/AGENTS.md` warns this repo's Next.js has breaking changes
> vs. training data — read `node_modules/next/dist/docs/` before touching web code. The
> web app deliberately does **not** use the Vercel AI SDK; keep the hand-rolled SSE
> pattern for consistency.

## 8. Cost & safety guardrails

- **Cheap default model** (`CALYPR_ASSISTANT_MODEL`), `max_tokens` capped, temperature low
  (~0.2) — spec-shaped JSON, not creative writing.
- **Metering:** stream `usage` events now; when the `run`/`run_usage` tables exist
  (MVP-EXECUTION-PLAN.md Week 2), persist assist calls as rows with `source="assist"` so
  they count against plan caps. Add a per-workspace daily assist cap
  (`CALYPR_ASSIST_DAILY_CAP`, default 50) enforced in the router even before billing.
- **Injection surface:** assistant output only ever becomes a **validated GraphSpec** —
  never executed code, never a DB write beyond the normal save flow. `code` nodes
  forbidden in v1 (§5.1). Prompt content is user-supplied; nothing from it is interpolated
  into shell/SQL.
- **No key, no feature:** with no provider key, `/assist` uses the fake path (below) in
  dev/CI and returns a clear 503-style `error` event in prod.

## 9. Keyless fake path (CI/e2e — non-negotiable, matches repo convention)

`FakeAssistant` in `calypr_assistant`: deterministic keyword → template mapping, e.g.
"rag"/"knowledge"/"docs" → the RAG framework spec; "route"/"classify" → the Router
template; "team"/"parallel"/"research" → Orchestrator–Worker; anything else → the basic
Input→Agent→Output golden spec (`services/compiler/golden.py`). Refine mode with "add a
router" appends deterministic changes where trivial, else returns the mapped template.
Emits the full event sequence including fake `usage`, so the panel is fully exercisable
offline.

## 10. Tests ("done" gates)

- **pytest (`services/assistant/tests/`):** prompt builder includes all 12 registry types
  and excludes none; parse handles fenced/noisy JSON; repair loop feeds issues back and
  succeeds on 2nd attempt (fake model scripted invalid-then-valid); `code`-node output is
  rejected; provider routing test for `kimi-*`/`deepseek-*` ids in `services/model/tests`.
- **API test:** `/assist` streams `status → graph → usage → [DONE]` with the fake path;
  tenant dep enforced; daily cap returns the right error.
- **Playwright `e2e/tests/phase9-assistant.spec.ts`** (keyless): open canvas → assistant
  rail icon → type "I would like a RAG chatbot for my website" → send → canvas shows
  Input/Retriever/Agent/Output wired left-to-right → "Try it" streams a reply (fake model)
  → Code tab shows generated Python containing a retriever → "Restore previous" empties
  back to the prior graph.
- **Optional live test** (env-gated, like the existing OpenAI live test): one real call to
  each configured provider producing a valid spec.

## 11. Files to create / modify (summary)

| Action | Path |
|---|---|
| create | `services/assistant/src/calypr_assistant/{__init__,prompt,draft,fake,events}.py` + `pyproject.toml` + tests (register in `uv` workspace) |
| create | `apps/api/src/calypr_api/routers/assist.py` (+ register in `main.py`, schema in `schemas.py`, settings entries) |
| modify | `services/model/src/calypr_model/{factory,openai_client}.py` (base_url/api_key params, kimi/deepseek routing) |
| create | `apps/web/src/app/api/assist/route.ts` (SSE proxy) |
| modify | `apps/web/src/components/canvas/AssistantPanel.tsx` (scaffold → functional), `apps/web/src/lib/api.ts` (`assistAgent`) |
| reuse | spec→flow conversion + auto-layout in `apps/web/src/lib/graph.ts` (via the TemplatesPanel path — no new layout code) |
| create | `e2e/tests/phase9-assistant.spec.ts` |

## 12. Non-goals (v1)

Surgical graph edits (node-level diffs); assistant-generated Custom Code nodes; multi-turn
tool use by the assistant; voice; auto-saving generated graphs; per-node model suggestions
beyond what the few-shots teach; streaming *partial* graphs onto the canvas (all-or-nothing
apply keeps validation meaningful).

## 13. Sequencing note

This feature was deliberately deferred in `MVP-EXECUTION-PLAN.md` (margin risk, roadmap
puts copilot depth in Month 4 behind the paid tier). Build it **after** Week-2 usage
persistence exists if possible — then assist calls are metered from day one. If built
earlier, the daily cap (§8) is the interim guardrail.
