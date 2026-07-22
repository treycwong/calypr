// Build a DSL GraphSpec from the canvas. We import the generated types from @calypr/dsl
// so the canvas and the Python engine share one contract (CLAUDE-PLAN.md §7).
import type { Edge, Node } from "@xyflow/react";

import type { GraphSpec, StateChannel } from "@calypr/dsl";

export type CalyprNodeType =
  | "input"
  | "agent"
  | "output"
  | "code"
  | "router"
  | "evaluator"
  | "memory"
  | "tool"
  | "responder"
  | "revisor"
  | "retriever"
  | "image"
  | "tts"
  | "upload";

export type NodeStatus = "active" | "done" | "error";

export type NodeData = {
  config: Record<string, unknown>;
  // Display-only run state injected at render time (see canvas decoration). Never persisted:
  // `buildGraphSpec` reads only `config`, so a run's status never leaks into the saved graph.
  status?: NodeStatus;
};

export const NODE_LABELS: Record<CalyprNodeType, string> = {
  input: "Input",
  agent: "Agent",
  output: "Output",
  code: "Custom Code",
  router: "Router",
  evaluator: "Evaluator",
  memory: "Memory",
  tool: "Tools",
  responder: "Responder",
  revisor: "Revisor",
  retriever: "Knowledge",
  image: "Image",
  tts: "Voice",
  upload: "Upload",
};

// 3rd-party tool providers a Tool node can run or generate. `demo_search` is deterministic
// and key-free; `tavily` runs live on the workspace's Tavily key (Settings → API Keys).
export const TOOL_PROVIDER_OPTIONS = [
  { value: "demo_search", label: "Demo search (no key, deterministic)" },
  { value: "tavily", label: "Tavily · web search" },
  { value: "mcp", label: "MCP server (HTTP)" },
  { value: "images_unsplash", label: "Unsplash · image search" },
  { value: "generic_http", label: "HTTP · any public GET API" },
];

// Transports an MCP Tool node can speak (HTTP only for now; stdio is code-gen-only, deferred).
export const MCP_TRANSPORT_OPTIONS = [
  { value: "streamable_http", label: "Streamable HTTP" },
  { value: "sse", label: "SSE" },
];

// The vector store a Knowledge (RAG) node retrieves from. `demo` is a seeded in-memory store
// (no key, deterministic); `pgvector` is code-gen only for now — the generated code retrieves
// from the user's own Postgres + a knowledge-base collection.
export const KNOWLEDGE_SOURCE_OPTIONS = [
  { value: "demo", label: "Demo KB (no key, deterministic)" },
  { value: "pgvector", label: "pgvector · your Postgres (code-gen)" },
];

// A Router decides a branch either by Python rules over state, or by an LLM classifier
// (the "routing agent" pattern) that picks the best branch for the request.
export const ROUTER_KIND_OPTIONS = [
  { value: "rules", label: "Rules — Python conditions over state" },
  { value: "llm", label: "LLM — a classifier picks the branch" },
];

// `byoProvider` marks a *frontier* model: it runs only on the workspace's own API key, is not
// part of the metered pricing model, and the picker disables it until that key is on file.
// The server enforces this independently (apps/api `model_access.py`) — this is just the UI.
export const MODEL_OPTIONS: {
  value: string;
  label: string;
  byoProvider?: string;
}[] = [
  { value: "fake", label: "Fake (no key, deterministic)" },
  { value: "gpt-4o-mini", label: "OpenAI · gpt-4o-mini" },
  { value: "gpt-4o", label: "OpenAI · gpt-4o" },
  { value: "claude-sonnet-4-5", label: "Anthropic · claude-sonnet-4-5" },
  {
    value: "kimi-k3",
    label: "Moonshot · kimi-k3 (reasoning, 1M ctx)",
    byoProvider: "moonshot",
  },
  {
    value: "claude-opus-4-8",
    label: "Anthropic · Claude Opus 4.8",
    byoProvider: "anthropic",
  },
];

// Image-generation models for the Image node. `fake` is key-free (a 1×1 PNG) for previewing the
// wiring; the gpt-image-* models call OpenAI and are token-billed.
export const IMAGE_MODEL_OPTIONS = [
  { value: "fake", label: "Fake (no key, 1×1 preview)" },
  { value: "gpt-image-2", label: "OpenAI · gpt-image-2" },
  { value: "gpt-image-1.5", label: "OpenAI · gpt-image-1.5" },
  { value: "gpt-image-1-mini", label: "OpenAI · gpt-image-1-mini" },
  { value: "gpt-image-1", label: "OpenAI · gpt-image-1 (legacy)" },
];

// Sizes the gpt-image models support (plus `auto`). Portrait/landscape mirror the API's values.
export const IMAGE_SIZE_OPTIONS = [
  { value: "auto", label: "Auto" },
  { value: "1024x1024", label: "Square · 1024×1024" },
  { value: "1024x1536", label: "Portrait · 1024×1536" },
  { value: "1536x1024", label: "Landscape · 1536×1024" },
];

export const IMAGE_QUALITY_OPTIONS = [
  { value: "auto", label: "Auto" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

// Text-to-speech models for the Voice node. `fake` is key-free (a short silent clip) for previewing
// the wiring; gpt-4o-mini-tts adds tone steering (`instructions`); tts-1/-hd are the classic voices.
export const TTS_MODEL_OPTIONS = [
  { value: "fake", label: "Fake (no key, silent preview)" },
  { value: "gpt-4o-mini-tts", label: "OpenAI · gpt-4o-mini-tts" },
  { value: "tts-1", label: "OpenAI · tts-1" },
  { value: "tts-1-hd", label: "OpenAI · tts-1-hd" },
];

export const TTS_VOICE_OPTIONS = [
  { value: "alloy", label: "Alloy" },
  { value: "ash", label: "Ash" },
  { value: "ballad", label: "Ballad" },
  { value: "coral", label: "Coral" },
  { value: "echo", label: "Echo" },
  { value: "sage", label: "Sage" },
  { value: "shimmer", label: "Shimmer" },
  { value: "verse", label: "Verse" },
];

// The Russell & Norvig agent ladder — a preset that scaffolds the prompt and (for
// reflection/utility) an internal loop. Mirrors AgentConfig.agent_type in the engine.
export const AGENT_TYPE_OPTIONS = [
  { value: "simple_reflex", label: "Simple reflex — reacts to the latest input" },
  { value: "model_based", label: "Model-based — uses conversation state" },
  { value: "goal_based", label: "Goal-based — plans toward a goal" },
  { value: "utility_based", label: "Utility-based — picks the best of N" },
  { value: "learning", label: "Learning — adapts from feedback (experimental)" },
  { value: "reflection", label: "Reflection — critiques and revises itself" },
];

export const DEFAULT_CONFIG: Record<CalyprNodeType, Record<string, unknown>> = {
  input: { input_channel: "input", target_channel: "messages" },
  agent: {
    agent_type: "model_based",
    model: "gpt-4o-mini",
    label: "",
    system_prompt: "You are a helpful assistant.",
    input_channel: "messages",
    output_channel: "messages",
    max_steps: 8,
    max_reflections: 2,
    num_candidates: 3,
    goal: "",
  },
  output: { source_channel: "messages", output_channel: "output" },
  code: {
    code: 'last = state["messages"][-1]\nreturn {"messages": [AIMessage(content=last.content.upper())]}',
    imports: ["from langchain_core.messages import AIMessage"],
    input_channel: "messages",
    output_channel: "messages",
  },
  // Passthrough by default (always the `default` branch); add rules/branches + wire their
  // handles to branch. Auto-linking from a router labels the new edge with `default`. In
  // `llm` mode the classifier writes `route_channel` and the branch `when` is a description.
  router: {
    kind: "rules",
    input_channel: "input",
    branches: [],
    default: "next",
    model: "fake",
    route_channel: "task_type",
  },
  evaluator: {
    model: "fake",
    input_channel: "messages",
    criteria: "accuracy, clarity, and completeness",
    scale_max: 10,
    score_channel: "score",
    rationale_channel: "rationale",
  },
  memory: {
    operation: "buffer",
    input_channel: "messages",
    memory_channel: "memory",
    model: "fake",
  },
  tool: {
    provider: "demo_search",
    api_key: "",
    max_results: 3,
    mcp_url: "",
    mcp_transport: "streamable_http",
    mcp_token: "",
    mcp_tool_filter: [],
    mcp_connector_ref: "",
    http_url: "",
    http_method: "GET",
    http_params: {},
    jsonpath: "",
  },
  responder: { model: "fake", system_prompt: "" },
  revisor: { model: "fake", system_prompt: "", max_revisions: 2 },
  retriever: {
    source: "pgvector",
    collection: "",
    top_k: 4,
    embedding_model: "text-embedding-3-small",
    input_channel: "messages",
    output_channel: "context",
  },
  image: {
    model: "gpt-image-2",
    prompt_channel: "messages",
    output_channel: "messages",
    size: "1024x1024",
    quality: "auto",
    n: 1,
    style: "",
  },
  tts: {
    model: "gpt-4o-mini-tts",
    voice: "alloy",
    instructions: "",
    speed: 1,
    response_format: "mp3",
    input_channel: "messages",
    output_channel: "messages",
  },
  upload: {
    images_channel: "images",
    target_channel: "messages",
    max_images: 4,
  },
};

export const ROUTER_DEFAULT_BRANCH = String(DEFAULT_CONFIG.router.default);

// A branch on a Router node — `name` must match an outgoing edge's condition.
export type Branch = { name: string; when: string };

export function routerHandleNames(config: Record<string, unknown>): string[] {
  const branches = (config.branches as Branch[] | undefined) ?? [];
  const names = branches.map((b) => b.name).filter(Boolean);
  const fallback = String(config.default ?? "");
  if (fallback && !names.includes(fallback)) names.push(fallback);
  return names.length ? names : [ROUTER_DEFAULT_BRANCH];
}

// Phase 2 uses a fixed default state; a State editor for custom channels comes later. The
// extra channels back the Evaluator (score/rationale), Memory (memory), and Knowledge
// (context) nodes. (The engine also unions node-declared channels at compile time, so an
// incomplete client state can't drop them — this list just keeps the canvas self-consistent.)
const DEFAULT_STATE: StateChannel[] = [
  { key: "input", type: "string", reducer: "last" },
  { key: "messages", type: "messages", reducer: "append" },
  { key: "output", type: "string", reducer: "last" },
  { key: "score", type: "number", reducer: "last" },
  { key: "rationale", type: "string", reducer: "last" },
  { key: "memory", type: "list", reducer: "append" },
  { key: "context", type: "string", reducer: "last" },
  { key: "task_type", type: "string", reducer: "last" },
];

// Auto-layout: place nodes in left→right columns by their distance (depth) from the entry, and
// spread nodes that share a column vertically. This makes fan-out (orchestrator → N parallel
// workers) visible instead of a single stack. Used only when the GraphSpec carries no explicit
// positions (i.e. a template); saved agents keep their positions.
function layeredLayout(
  nodes: GraphSpec["nodes"],
  edges: GraphSpec["edges"],
  entry: GraphSpec["entry"],
): Map<string, { x: number; y: number }> {
  const ns = nodes ?? [];
  const es = edges ?? [];
  const adj = new Map<string, string[]>();
  const indeg = new Map<string, number>();
  for (const n of ns) {
    adj.set(n.id, []);
    indeg.set(n.id, 0);
  }
  for (const e of es) {
    adj.get(e.source)?.push(e.target);
    indeg.set(e.target, (indeg.get(e.target) ?? 0) + 1);
  }
  // Roots: the entry, else any node with no incoming edge, else the first node.
  const roots = entry
    ? [entry]
    : ns.filter((n) => (indeg.get(n.id) ?? 0) === 0).map((n) => n.id);
  const start = roots.length ? roots : ns.slice(0, 1).map((n) => n.id);

  // BFS first-visit depth (a back-edge in a loop doesn't re-deepen a visited node).
  const depth = new Map<string, number>();
  const queue: string[] = [];
  for (const r of start) {
    depth.set(r, 0);
    queue.push(r);
  }
  while (queue.length) {
    const id = queue.shift() as string;
    const d = depth.get(id) ?? 0;
    for (const t of adj.get(id) ?? []) {
      if (!depth.has(t)) {
        depth.set(t, d + 1);
        queue.push(t);
      }
    }
  }
  for (const n of ns) if (!depth.has(n.id)) depth.set(n.id, 0);

  const columns = new Map<number, string[]>();
  for (const n of ns) {
    const c = depth.get(n.id) ?? 0;
    const col = columns.get(c) ?? [];
    col.push(n.id);
    columns.set(c, col);
  }

  const COL_W = 260;
  const ROW_H = 130;
  const pos = new Map<string, { x: number; y: number }>();
  for (const [c, ids] of columns) {
    ids.forEach((id, i) => {
      pos.set(id, { x: 60 + c * COL_W, y: 300 + (i - (ids.length - 1) / 2) * ROW_H });
    });
  }
  return pos;
}

// The inverse of buildGraphSpec: hydrate the canvas from a GraphSpec (e.g. a template).
export function graphToCanvas(graph: GraphSpec): {
  nodes: Node<NodeData>[];
  edges: Edge[];
} {
  const specNodes = graph.nodes ?? [];
  // Honor saved positions; otherwise auto-place left→right by graph depth so fan-out is visible.
  const hasPositions = specNodes.some((n) => n.position?.x != null);
  const auto = hasPositions
    ? null
    : layeredLayout(graph.nodes, graph.edges, graph.entry);
  const nodes: Node<NodeData>[] = specNodes.map((n, i) => ({
    id: n.id,
    type: n.type as CalyprNodeType,
    position: auto?.get(n.id) ?? {
      x: (n.position?.x as number | undefined) ?? 280,
      y: (n.position?.y as number | undefined) ?? 30 + i * 130,
    },
    data: { config: { ...(n.config ?? {}) } },
  }));
  const edges: Edge[] = (graph.edges ?? []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    ...(e.condition ? { label: e.condition } : {}),
  }));
  return { nodes, edges };
}

export function buildGraphSpec(
  nodes: Node<NodeData>[],
  edges: Edge[],
  name = "Untitled Agent",
): GraphSpec {
  const entry = nodes.find((n) => n.type === "input");
  return {
    schema_version: "0.1.0",
    id: "canvas-agent",
    name,
    state: DEFAULT_STATE,
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type as string,
      config: n.data.config,
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
    })),
    // A Router's out-edges carry a branch name (the edge label) as `condition`.
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      ...(e.label ? { condition: String(e.label) } : {}),
    })),
    entry: entry ? entry.id : null,
  };
}
