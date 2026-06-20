"use client";

import { Handle, type NodeProps, Position } from "@xyflow/react";
import type { ReactNode } from "react";

import type { NodeData } from "@/lib/graph";

const handleStyle = { width: 10, height: 10 };

function Shell({
  title,
  accent,
  selected,
  children,
}: {
  title: string;
  accent: string;
  selected?: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      className={`min-w-[168px] rounded-lg border bg-card px-3 py-2 shadow-sm transition ${
        selected ? "border-primary ring-2 ring-primary/30" : "border-border"
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
      <Shell title="Input" accent="bg-sky-500" selected={selected}>
        chat entry
      </Shell>
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </>
  );
}

export function AgentNodeView({ data, selected }: NodeProps) {
  const model = (data as NodeData).config.model ?? "fake";
  return (
    <>
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <Shell title="Agent" accent="bg-violet-500" selected={selected}>
        model: {String(model)}
      </Shell>
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </>
  );
}

export function OutputNodeView({ selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <Shell title="Output" accent="bg-emerald-500" selected={selected}>
        response
      </Shell>
    </>
  );
}

export function CodeNodeView({ selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <Shell title="Custom Code" accent="bg-amber-500" selected={selected}>
        python · no ceiling
      </Shell>
      <Handle type="source" position={Position.Bottom} style={handleStyle} />
    </>
  );
}

export const nodeTypes = {
  input: InputNodeView,
  agent: AgentNodeView,
  output: OutputNodeView,
  code: CodeNodeView,
};
