"use client";

import type { Node } from "@xyflow/react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type CalyprNodeType,
  MODEL_OPTIONS,
  NODE_LABELS,
  type NodeData,
} from "@/lib/graph";

export function ConfigPanel({
  node,
  onChange,
}: {
  node: Node<NodeData> | null;
  onChange: (config: Record<string, unknown>) => void;
}) {
  if (!node) {
    return (
      <div className="text-sm text-muted-foreground">
        Select a block to configure it.
      </div>
    );
  }

  const type = node.type as CalyprNodeType;
  const config = node.data.config;
  const set = (patch: Record<string, unknown>) => onChange({ ...config, ...patch });

  return (
    <div className="space-y-4">
      <div className="text-sm font-medium">{NODE_LABELS[type]} settings</div>

      {type === "agent" ? (
        <>
          <div className="space-y-1.5">
            <Label htmlFor="cfg-model">Model</Label>
            <select
              id="cfg-model"
              data-testid="cfg-model"
              className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={String(config.model ?? "fake")}
              onChange={(e) => set({ model: e.target.value })}
            >
              {MODEL_OPTIONS.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cfg-prompt">System prompt</Label>
            <Textarea
              id="cfg-prompt"
              data-testid="cfg-prompt"
              rows={4}
              value={String(config.system_prompt ?? "")}
              onChange={(e) => set({ system_prompt: e.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="cfg-steps">Max steps</Label>
            <Input
              id="cfg-steps"
              type="number"
              min={1}
              value={Number(config.max_steps ?? 8)}
              onChange={(e) => set({ max_steps: Number(e.target.value) })}
            />
          </div>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">
          {type === "input"
            ? "Seeds the conversation from the user's message."
            : "Returns the agent's final reply."}
        </p>
      )}
    </div>
  );
}
