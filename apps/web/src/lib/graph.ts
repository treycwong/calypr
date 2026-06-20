// Build a DSL GraphSpec from the canvas. We import the generated types from @calypr/dsl
// so the canvas and the Python engine share one contract (CLAUDE-PLAN.md §7).
import type { Edge, Node } from "@xyflow/react";

import type { GraphSpec, StateChannel } from "@calypr/dsl";

export type CalyprNodeType = "input" | "agent" | "output";

export type NodeData = {
  config: Record<string, unknown>;
};

export const NODE_LABELS: Record<CalyprNodeType, string> = {
  input: "Input",
  agent: "Agent",
  output: "Output",
};

export const MODEL_OPTIONS = [
  { value: "fake", label: "Fake (no key, deterministic)" },
  { value: "gpt-4o-mini", label: "OpenAI · gpt-4o-mini" },
  { value: "gpt-4o", label: "OpenAI · gpt-4o" },
  { value: "claude-sonnet-4-5", label: "Anthropic · claude-sonnet-4-5" },
];

export const DEFAULT_CONFIG: Record<CalyprNodeType, Record<string, unknown>> = {
  input: { input_channel: "input", target_channel: "messages" },
  agent: {
    model: "fake",
    system_prompt: "You are a helpful assistant.",
    input_channel: "messages",
    output_channel: "messages",
    max_steps: 8,
  },
  output: { source_channel: "messages", output_channel: "output" },
};

// Phase 2 uses a fixed default state; a State editor for custom channels comes later.
const DEFAULT_STATE: StateChannel[] = [
  { key: "input", type: "string", reducer: "last" },
  { key: "messages", type: "messages", reducer: "append" },
  { key: "output", type: "string", reducer: "last" },
];

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
    edges: edges.map((e) => ({ id: e.id, source: e.source, target: e.target })),
    entry: entry ? entry.id : null,
  };
}
