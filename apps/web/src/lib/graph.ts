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
  | "revisor";

export type NodeData = {
  config: Record<string, unknown>;
};

export const NODE_LABELS: Record<CalyprNodeType, string> = {
  input: "Input",
  agent: "Agent",
  output: "Output",
  code: "Custom Code",
  router: "If-Else",
  evaluator: "Evaluator",
  memory: "Memory",
  tool: "Tools",
  responder: "Responder",
  revisor: "Revisor",
};

// 3rd-party tool providers a Tool node can run or generate. `demo_search` is deterministic
// and key-free; `tavily` is code-gen only for now (runs in the generated code with a key).
export const TOOL_PROVIDER_OPTIONS = [
  { value: "demo_search", label: "Demo search (no key, deterministic)" },
  { value: "tavily", label: "Tavily · web search (code-gen)" },
];

export const MODEL_OPTIONS = [
  { value: "fake", label: "Fake (no key, deterministic)" },
  { value: "gpt-4o-mini", label: "OpenAI · gpt-4o-mini" },
  { value: "gpt-4o", label: "OpenAI · gpt-4o" },
  { value: "claude-sonnet-4-5", label: "Anthropic · claude-sonnet-4-5" },
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
    model: "fake",
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
  // Passthrough by default (always the `default` branch); add rules + wire their handles
  // to branch. Auto-linking from a router labels the new edge with `default`.
  router: { kind: "rules", input_channel: "input", branches: [], default: "next" },
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
  tool: { provider: "demo_search", api_key: "", max_results: 3 },
  responder: { model: "fake", system_prompt: "" },
  revisor: { model: "fake", system_prompt: "", max_revisions: 2 },
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
// extra channels back the Evaluator (score/rationale) and Memory (memory) nodes.
const DEFAULT_STATE: StateChannel[] = [
  { key: "input", type: "string", reducer: "last" },
  { key: "messages", type: "messages", reducer: "append" },
  { key: "output", type: "string", reducer: "last" },
  { key: "score", type: "number", reducer: "last" },
  { key: "rationale", type: "string", reducer: "last" },
  { key: "memory", type: "list", reducer: "append" },
];

// The inverse of buildGraphSpec: hydrate the canvas from a GraphSpec (e.g. a template).
export function graphToCanvas(graph: GraphSpec): {
  nodes: Node<NodeData>[];
  edges: Edge[];
} {
  const nodes: Node<NodeData>[] = (graph.nodes ?? []).map((n, i) => ({
    id: n.id,
    type: n.type as CalyprNodeType,
    position: {
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
