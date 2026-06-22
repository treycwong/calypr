"use client";

import type { Node } from "@xyflow/react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  AGENT_TYPE_OPTIONS,
  type Branch,
  type CalyprNodeType,
  MODEL_OPTIONS,
  NODE_LABELS,
  type NodeData,
} from "@/lib/graph";

type Setter = (patch: Record<string, unknown>) => void;
type Config = Record<string, unknown>;

function Field({
  id,
  label,
  children,
}: {
  id: string;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
    </div>
  );
}

function SelectField({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <Field id={id} label={label}>
      <select
        id={id}
        data-testid={id}
        className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

function ModelField({ config, set }: { config: Config; set: Setter }) {
  return (
    <SelectField
      id="cfg-model"
      label="Model"
      value={String(config.model ?? "fake")}
      options={MODEL_OPTIONS}
      onChange={(v) => set({ model: v })}
    />
  );
}

function AgentFields({ config, set }: { config: Config; set: Setter }) {
  const agentType = String(config.agent_type ?? "model_based");
  return (
    <>
      <SelectField
        id="cfg-agent-type"
        label="Agent type"
        value={agentType}
        options={AGENT_TYPE_OPTIONS}
        onChange={(v) => set({ agent_type: v })}
      />
      <ModelField config={config} set={set} />
      <Field id="cfg-prompt" label="System prompt">
        <Textarea
          id="cfg-prompt"
          data-testid="cfg-prompt"
          rows={4}
          value={String(config.system_prompt ?? "")}
          onChange={(e) => set({ system_prompt: e.target.value })}
        />
      </Field>

      {agentType === "reflection" ? (
        <Field id="cfg-max-reflections" label="Max reflections">
          <Input
            id="cfg-max-reflections"
            data-testid="cfg-max-reflections"
            type="number"
            min={0}
            value={Number(config.max_reflections ?? 2)}
            onChange={(e) => set({ max_reflections: Number(e.target.value) })}
          />
        </Field>
      ) : null}

      {agentType === "utility_based" ? (
        <Field id="cfg-num-candidates" label="Candidates (best of N)">
          <Input
            id="cfg-num-candidates"
            data-testid="cfg-num-candidates"
            type="number"
            min={1}
            value={Number(config.num_candidates ?? 3)}
            onChange={(e) => set({ num_candidates: Number(e.target.value) })}
          />
        </Field>
      ) : null}

      {agentType === "goal_based" ? (
        <Field id="cfg-goal" label="Goal">
          <Input
            id="cfg-goal"
            data-testid="cfg-goal"
            value={String(config.goal ?? "")}
            onChange={(e) => set({ goal: e.target.value })}
          />
        </Field>
      ) : null}
    </>
  );
}

function RouterFields({ config, set }: { config: Config; set: Setter }) {
  const branches = (config.branches as Branch[] | undefined) ?? [];
  const setBranch = (i: number, patch: Partial<Branch>) =>
    set({ branches: branches.map((b, j) => (j === i ? { ...b, ...patch } : b)) });
  return (
    <>
      <Field id="cfg-input-channel" label="Reads channel">
        <Input
          id="cfg-input-channel"
          value={String(config.input_channel ?? "input")}
          onChange={(e) => set({ input_channel: e.target.value })}
        />
      </Field>

      <div className="space-y-2">
        <Label>Branches</Label>
        <p className="text-xs text-muted-foreground">
          Each rule is a Python expression over <code>state</code>. Wire each branch
          handle to its target; unmatched input takes the default.
        </p>
        {branches.map((b, i) => (
          <div key={i} className="space-y-1 rounded-md border border-border p-2">
            <Input
              aria-label={`branch ${i} name`}
              placeholder="branch name"
              value={b.name}
              onChange={(e) => setBranch(i, { name: e.target.value })}
            />
            <Input
              aria-label={`branch ${i} rule`}
              className="font-mono text-xs"
              placeholder={'"urgent" in state["input"].lower()'}
              value={b.when}
              onChange={(e) => setBranch(i, { when: e.target.value })}
            />
            <Button
              variant="ghost"
              size="sm"
              onClick={() => set({ branches: branches.filter((_, j) => j !== i) })}
            >
              Remove
            </Button>
          </div>
        ))}
        <Button
          variant="outline"
          size="sm"
          data-testid="add-branch"
          onClick={() => set({ branches: [...branches, { name: "", when: "" }] })}
        >
          + Add branch
        </Button>
      </div>

      <Field id="cfg-router-default" label="Default branch">
        <Input
          id="cfg-router-default"
          data-testid="cfg-router-default"
          value={String(config.default ?? "")}
          onChange={(e) => set({ default: e.target.value })}
        />
      </Field>
    </>
  );
}

function EvaluatorFields({ config, set }: { config: Config; set: Setter }) {
  return (
    <>
      <ModelField config={config} set={set} />
      <Field id="cfg-criteria" label="Criteria (rubric)">
        <Textarea
          id="cfg-criteria"
          data-testid="cfg-criteria"
          rows={3}
          value={String(config.criteria ?? "")}
          onChange={(e) => set({ criteria: e.target.value })}
        />
      </Field>
      <Field id="cfg-scale-max" label="Scale max">
        <Input
          id="cfg-scale-max"
          type="number"
          min={1}
          value={Number(config.scale_max ?? 10)}
          onChange={(e) => set({ scale_max: Number(e.target.value) })}
        />
      </Field>
    </>
  );
}

function MemoryFields({ config, set }: { config: Config; set: Setter }) {
  const op = String(config.operation ?? "buffer");
  return (
    <>
      <SelectField
        id="cfg-operation"
        label="Operation"
        value={op}
        options={[
          { value: "buffer", label: "Buffer — append each turn" },
          { value: "summary", label: "Summary — condense with the model" },
        ]}
        onChange={(v) => set({ operation: v })}
      />
      <Field id="cfg-memory-channel" label="Memory channel">
        <Input
          id="cfg-memory-channel"
          value={String(config.memory_channel ?? "memory")}
          onChange={(e) => set({ memory_channel: e.target.value })}
        />
      </Field>
      {op === "summary" ? <ModelField config={config} set={set} /> : null}
    </>
  );
}

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
  const set: Setter = (patch) => onChange({ ...config, ...patch });

  return (
    <div className="space-y-4">
      <div className="text-sm font-medium">{NODE_LABELS[type]} settings</div>

      {type === "agent" ? <AgentFields config={config} set={set} /> : null}
      {type === "router" ? <RouterFields config={config} set={set} /> : null}
      {type === "evaluator" ? <EvaluatorFields config={config} set={set} /> : null}
      {type === "memory" ? <MemoryFields config={config} set={set} /> : null}

      {type === "code" ? (
        <Field id="cfg-code" label="Python — a function body over `state`">
          <Textarea
            id="cfg-code"
            data-testid="cfg-code"
            rows={8}
            className="font-mono text-xs"
            value={String(config.code ?? "")}
            onChange={(e) => set({ code: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">
            Return a dict of state updates. This block round-trips verbatim into the
            generated code — your no-ceiling escape hatch.
          </p>
        </Field>
      ) : null}

      {type === "input" || type === "output" ? (
        <p className="text-xs text-muted-foreground">
          {type === "input"
            ? "Seeds the conversation from the user's message."
            : "Returns the agent's final reply."}
        </p>
      ) : null}
    </div>
  );
}
