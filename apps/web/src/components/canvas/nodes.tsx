"use client";

import { Handle, type NodeProps, Position } from "@xyflow/react";
import type { ReactNode } from "react";

import { type NodeData, routerHandleNames } from "@/lib/graph";

const handleStyle = { width: 10, height: 10 };

// Flow runs left → right: inputs enter on the Left, outputs leave on the Right.
function Shell({
  title,
  accent,
  selected,
  testid,
  children,
}: {
  title: string;
  accent: string;
  selected?: boolean;
  testid?: string;
  children?: ReactNode;
}) {
  return (
    <div
      data-testid={testid}
      className={`min-w-[168px] rounded-lg border bg-card px-3 py-2 shadow-sm transition ${
        selected
          ? "border-cyan-400 shadow-[0_0_0_1px_rgb(34_211_238),0_0_22px_-2px_rgb(34_211_238/0.6)]"
          : "border-border hover:border-muted-foreground/40"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${accent}`} />
        <span className="text-sm font-medium">{title}</span>
      </div>
      {children ? (
        <div className="mt-1 truncate text-xs text-muted-foreground">{children}</div>
      ) : null}
    </div>
  );
}

export function InputNodeView({ selected }: NodeProps) {
  return (
    <>
      <Shell title="Input" accent="bg-sky-500" selected={selected} testid="node-input">
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
      <Shell title={title} accent="bg-violet-500" selected={selected} testid="node-agent">
        {String(config.agent_type ?? "model_based")} · {String(config.model ?? "fake")}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function OutputNodeView({ selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Output"
        accent="bg-emerald-500"
        selected={selected}
        testid="node-output"
      >
        response
      </Shell>
    </>
  );
}

export function CodeNodeView({ selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Custom Code"
        accent="bg-amber-500"
        selected={selected}
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
      <Shell title="Router" accent="bg-rose-500" selected={selected} testid="node-router">
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
        accent="bg-orange-500"
        selected={selected}
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
      <Shell title="Memory" accent="bg-teal-500" selected={selected} testid="node-memory">
        {String(op)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function ToolNodeView({ data, selected }: NodeProps) {
  const provider = (data as NodeData).config.provider ?? "demo_search";
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Tools" accent="bg-yellow-500" selected={selected} testid="node-tool">
        {String(provider)}
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
        accent="bg-lime-500"
        selected={selected}
        testid="node-retriever"
      >
        RAG · {String(source)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function ResponderNodeView({ selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Responder"
        accent="bg-indigo-500"
        selected={selected}
        testid="node-responder"
      >
        draft + self-critique
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function RevisorNodeView({ selected }: NodeProps) {
  // Branches: "revise" (loop) and "done" (finish), spread down the Right edge — labelled edges
  // carry the names.
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Revisor"
        accent="bg-fuchsia-500"
        selected={selected}
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
      <Shell title="Image" accent="bg-pink-500" selected={selected} testid="node-image">
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
      <Shell title="Voice" accent="bg-purple-500" selected={selected} testid="node-tts">
        {String(config.model ?? "gpt-4o-mini-tts")} · {String(config.voice ?? "alloy")}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export const nodeTypes = {
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
  tts: TTSNodeView,
};
