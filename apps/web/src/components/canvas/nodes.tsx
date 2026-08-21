"use client";

import { Handle, type NodeProps, Position } from "@xyflow/react";
import type { ComponentType, ReactNode } from "react";

import { NODE_STYLE } from "@/components/canvas/node-style";
import {
  type CalyprNodeType,
  type NodeData,
  type NodeStatus,
  routerHandleNames,
} from "@/lib/graph";
import { useConnectors } from "@/lib/use-connectors";

const handleStyle = { width: 10, height: 10 };

// Run-state styling, layered above the idle/selected border. `active` pulses (see canvas.css
// `nodePulse`); `done`/`error` settle to a persistent ring until the next run clears them.
const STATUS_CLASS: Record<NodeStatus, string> = {
  active:
    "border-cyan-400 shadow-[0_0_0_1px_rgb(34_211_238),0_0_26px_-2px_rgb(34_211_238/0.7)] animate-[nodePulse_1.2s_ease-in-out_infinite]",
  done: "border-emerald-500/60 shadow-[0_0_0_1px_rgb(16_185_129/0.4)]",
  error: "border-red-500 shadow-[0_0_0_1px_rgb(239_68_68/0.6)]",
};

function statusOf(data: unknown): NodeStatus | undefined {
  return (data as NodeData | undefined)?.status;
}

// Flow runs left → right: inputs enter on the Left, outputs leave on the Right.
function Shell({
  title,
  type,
  selected,
  status,
  testid,
  children,
}: {
  title: string;
  type: CalyprNodeType;
  selected?: boolean;
  status?: NodeStatus;
  testid?: string;
  children?: ReactNode;
}) {
  // The icon comes from the same map the Blocks palette reads, so the card you picked in the
  // sidebar is visibly the card that landed here. It replaced a 2px coloured dot whose colour was
  // hardcoded at each of the fourteen call sites — and it is monochrome, which leaves the canvas
  // free to use colour for run state alone (the cyan active glow, the emerald done ring).
  const { icon: Icon } = NODE_STYLE[type];
  // A run status takes visual priority over selection so you can watch execution move even while
  // a node is selected; otherwise fall back to the selected glow, then idle.
  // The background is part of this rather than a constant `bg-card` on the base class: two
  // background utilities on one element are decided by their order in Tailwind's output, not by
  // the class attribute, so the selected wash would win or lose unpredictably.
  const stateClass = status
    ? `bg-card ${STATUS_CLASS[status]}`
    : selected
      ? // Neutral, not cyan. Cyan is the running state on this canvas — using it for selection
        // too meant a selected node and a running node looked the same, and a graph you had
        // clicked around looked like it was mid-run.
        //
        // **Opaque.** This was a translucent white wash, which let the wires behind the card
        // show straight through it — selecting a node in a busy part of the graph made it
        // harder to read, not easier. A card is a solid object.
        "bg-neutral-700 border-white/60 shadow-[0_0_0_1px_rgb(255_255_255/0.25)]"
      : "bg-card border-border hover:border-muted-foreground/40";
  return (
    <div
      data-testid={testid}
      data-status={status ?? undefined}
      // `transition-colors duration-75`, not a bare `transition`. The bare utility animates every
      // animatable property — box-shadow and background included — over 150ms, so a click landed
      // its state change in ~45ms and then took another 150ms to *look* selected. That reads as
      // lag. 75ms is enough to stop the hover border snapping, and short enough that selection
      // feels immediate.
      className={`min-w-[168px] rounded-lg border px-3 py-2 shadow-sm transition-colors duration-75 ${stateClass}`}
    >
      <div className="flex items-center gap-2">
        <Icon
          className={`h-3.5 w-3.5 shrink-0 ${status === "active" ? "animate-pulse" : ""}`}
        />
        <span className="text-sm font-medium">{title}</span>
      </div>
      {children ? (
        <div className="mt-1 truncate text-xs text-muted-foreground">{children}</div>
      ) : null}
    </div>
  );
}

export function InputNodeView({ data, selected }: NodeProps) {
  return (
    <>
      <Shell
        title="Input"
        type="input"
        selected={selected}
        status={statusOf(data)}
        testid="node-input"
      >
        chat entry
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function AgentNodeView({ data, selected }: NodeProps) {
  const config = (data as NodeData).config;
  // A role-specialized agent (e.g. "Orchestrator") shows its label; a bare agent shows "Agent".
  const title = String(config.label || "Agent");
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title={title} type="agent" selected={selected} status={statusOf(data)} testid="node-agent">
        {String(config.agent_type ?? "model_based")} · {String(config.model ?? "fake")}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function OutputNodeView({ data, selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Output"
        type="output"
        selected={selected}
        status={statusOf(data)}
        testid="node-output"
      >
        response
      </Shell>
    </>
  );
}

export function CodeNodeView({ data, selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Custom Code"
        type="code"
        selected={selected}
        status={statusOf(data)}
        testid="node-code"
      >
        python · no ceiling
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function RouterNodeView({ data, selected }: NodeProps) {
  // One named source handle per branch (+ the default), spread down the Right edge — wire each
  // to its target; the edge label becomes the branch `condition` in the GraphSpec.
  const config = (data as NodeData).config;
  const names = routerHandleNames(config);
  const isLlm = String(config.kind ?? "rules") === "llm";
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Router" type="router" selected={selected} status={statusOf(data)} testid="node-router">
        {(isLlm ? ["llm", ...names] : names).join(" · ")}
      </Shell>
      {names.map((name, i) => (
        <Handle
          key={name}
          id={name}
          type="source"
          position={Position.Right}
          style={{
            ...handleStyle,
            top: `${((i + 1) / (names.length + 1)) * 100}%`,
          }}
        />
      ))}
    </>
  );
}

export function EvaluatorNodeView({ data, selected }: NodeProps) {
  const max = (data as NodeData).config.scale_max ?? 10;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Evaluator"
        type="evaluator"
        selected={selected}
        status={statusOf(data)}
        testid="node-evaluator"
      >
        LLM judge · 1–{String(max)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function MemoryNodeView({ data, selected }: NodeProps) {
  const op = (data as NodeData).config.operation ?? "buffer";
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Memory" type="memory" selected={selected} status={statusOf(data)} testid="node-memory">
        {String(op)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function ToolNodeView({ data, selected }: NodeProps) {
  const config = (data as NodeData).config;
  const provider = config.provider ?? "demo_search";
  const connectors = useConnectors();
  // For MCP, show where the tools come from next to the provider tag. A connector-backed node
  // has no `mcp_url` on the client — the ref is all the canvas stores, and the server resolves
  // it to a URL at run time — so name the connector instead of reading a URL that is never
  // there. "(no server)" is reserved for a node that genuinely has neither.
  let label = String(provider);
  if (provider === "mcp") {
    const ref = String(config.mcp_connector_ref ?? "");
    const url = String(config.mcp_url ?? "");
    let host = "";
    try {
      host = url ? new URL(url).host : "";
    } catch {
      host = url;
    }
    if (ref) {
      // Until the list loads, say we have *a* connector rather than flashing "(no server)".
      const name = connectors.find((c) => c.id === ref)?.name;
      label = `mcp · ${name ?? "connector"}`;
    } else {
      label = host ? `mcp · ${host}` : "mcp · (no server)";
    }
  }
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Tools" type="tool" selected={selected} status={statusOf(data)} testid="node-tool">
        {label}
      </Shell>
      {/* Loops back to the agent that called it (the ReAct cycle). */}
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function RetrieverNodeView({ data, selected }: NodeProps) {
  const source = (data as NodeData).config.source ?? "demo";
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Knowledge"
        type="retriever"
        selected={selected}
        status={statusOf(data)}
        testid="node-retriever"
      >
        RAG · {String(source)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function ResponderNodeView({ data, selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Responder"
        type="responder"
        selected={selected}
        status={statusOf(data)}
        testid="node-responder"
      >
        draft + self-critique
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function RevisorNodeView({ data, selected }: NodeProps) {
  // Branches: "revise" (loop) and "done" (finish), spread down the Right edge — labelled edges
  // carry the names.
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Revisor"
        type="revisor"
        selected={selected}
        status={statusOf(data)}
        testid="node-revisor"
      >
        revise · loop
      </Shell>
      <Handle
        id="revise"
        type="source"
        position={Position.Right}
        style={{ ...handleStyle, top: "33%" }}
      />
      <Handle
        id="done"
        type="source"
        position={Position.Right}
        style={{ ...handleStyle, top: "67%" }}
      />
    </>
  );
}

export function ImageNodeView({ data, selected }: NodeProps) {
  const config = (data as NodeData).config;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Image" type="image" selected={selected} status={statusOf(data)} testid="node-image">
        {String(config.model ?? "gpt-image-2")} · {String(config.size ?? "1024x1024")}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function TTSNodeView({ data, selected }: NodeProps) {
  const config = (data as NodeData).config;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Voice" type="tts" selected={selected} status={statusOf(data)} testid="node-tts">
        {String(config.model ?? "gpt-4o-mini-tts")} · {String(config.voice ?? "alloy")}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function MeshNodeView({ data, selected }: NodeProps) {
  const config = (data as NodeData).config;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="3D" type="mesh" selected={selected} status={statusOf(data)} testid="node-mesh">
        {String(config.model ?? "fal-ai/trellis")} · image → glb
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function UploadNodeView({ data, selected }: NodeProps) {
  const max = (data as NodeData).config.max_images ?? 4;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Upload" type="upload" selected={selected} status={statusOf(data)} testid="node-upload">
        image in · up to {String(max)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

/**
 * Which component draws each block on the canvas.
 *
 * The `Record<CalyprNodeType, …>` annotation is load-bearing, not decoration. Without it this was
 * an untyped object literal, so a node type registered everywhere else — palette, config panel,
 * codegen, the API — but missing here rendered as an **empty card**: React Flow found no component
 * and drew the two connection handles with nothing between them. Nothing failed; the block was
 * simply invisible. Typed, a missing entry is a build error.
 */
export const nodeTypes: Record<CalyprNodeType, ComponentType<NodeProps>> = {
  input: InputNodeView,
  agent: AgentNodeView,
  output: OutputNodeView,
  code: CodeNodeView,
  router: RouterNodeView,
  evaluator: EvaluatorNodeView,
  memory: MemoryNodeView,
  tool: ToolNodeView,
  responder: ResponderNodeView,
  revisor: RevisorNodeView,
  retriever: RetrieverNodeView,
  image: ImageNodeView,
  mesh: MeshNodeView,
  tts: TTSNodeView,
  upload: UploadNodeView,
};
