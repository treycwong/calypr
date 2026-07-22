"use client";

import type { Node } from "@xyflow/react";
import { type ReactNode, useEffect, useState } from "react";

import { type Connector, listConnectors } from "@/lib/api";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  type Branch,
  type CalyprNodeType,
  IMAGE_MODEL_OPTIONS,
  IMAGE_QUALITY_OPTIONS,
  IMAGE_SIZE_OPTIONS,
  KNOWLEDGE_SOURCE_OPTIONS,
  MCP_TRANSPORT_OPTIONS,
  MODEL_OPTIONS,
  NODE_LABELS,
  type NodeData,
  ROUTER_KIND_OPTIONS,
  TOOL_PROVIDER_OPTIONS,
  TTS_MODEL_OPTIONS,
  TTS_VOICE_OPTIONS,
} from "@/lib/graph";
import { useProviderKeys } from "@/lib/use-provider-keys";

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
  options: { value: string; label: string; disabled?: boolean }[];
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
          <option key={o.value} value={o.value} disabled={o.disabled}>
            {o.label}
          </option>
        ))}
      </select>
    </Field>
  );
}

function ModelField({ config, set }: { config: Config; set: Setter }) {
  // Frontier models run only on the workspace's own key, so they stay disabled (with the
  // reason spelled out in the label) until that key is saved in Settings → API Keys.
  const { keyed } = useProviderKeys();
  const options = MODEL_OPTIONS.map((o) => {
    const locked = o.byoProvider !== undefined && !keyed.has(o.byoProvider);
    return locked
      ? { ...o, label: `${o.label} — add your own key in Settings`, disabled: true }
      : o;
  });
  return (
    <SelectField
      id="cfg-model"
      label="Model"
      value={String(config.model ?? "fake")}
      options={options}
      onChange={(v) => set({ model: v })}
    />
  );
}

function AgentFields({ config, set }: { config: Config; set: Setter }) {
  // The agent's character comes from the template (its agent_type); the panel shows the
  // model, prompt, and only the fields that type uses — no type selector.
  const agentType = String(config.agent_type ?? "model_based");
  return (
    <>
      <Field id="cfg-label" label="Name (optional)">
        <Input
          id="cfg-label"
          data-testid="cfg-label"
          placeholder="e.g. Orchestrator"
          value={String(config.label ?? "")}
          onChange={(e) => set({ label: e.target.value })}
        />
      </Field>
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
  const isLlm = String(config.kind ?? "rules") === "llm";
  const branches = (config.branches as Branch[] | undefined) ?? [];
  const setBranch = (i: number, patch: Partial<Branch>) =>
    set({ branches: branches.map((b, j) => (j === i ? { ...b, ...patch } : b)) });
  return (
    <>
      <SelectField
        id="cfg-router-kind"
        label="Decide by"
        value={String(config.kind ?? "rules")}
        options={ROUTER_KIND_OPTIONS}
        onChange={(v) => set({ kind: v })}
      />

      {isLlm ? <ModelField config={config} set={set} /> : null}

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
          {isLlm
            ? "Describe each branch in plain language — the classifier picks one. Wire each branch handle to its target; unmatched takes the default."
            : "Each rule is a Python expression over state. Wire each branch handle to its target; unmatched input takes the default."}
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
              aria-label={isLlm ? `branch ${i} description` : `branch ${i} rule`}
              className={isLlm ? "text-xs" : "font-mono text-xs"}
              placeholder={
                isLlm
                  ? "when the user wants a summary"
                  : '"urgent" in state["input"].lower()'
              }
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

function ToolFields({ config, set }: { config: Config; set: Setter }) {
  const provider = String(config.provider ?? "demo_search");
  const toolFilter = Array.isArray(config.mcp_tool_filter)
    ? (config.mcp_tool_filter as string[])
    : [];
  const connectorRef = String(config.mcp_connector_ref ?? "");
  const [connectors, setConnectors] = useState<Connector[]>([]);
  useEffect(() => {
    if (provider !== "mcp") return;
    listConnectors()
      .then(setConnectors)
      .catch(() => setConnectors([]));
  }, [provider]);
  const connectorOptions = [
    { value: "", label: "Manual URL (below)" },
    ...connectors.map((c) => ({
      value: c.id,
      label: `${c.name}${c.kind === "notion" ? " · Notion" : c.url ? ` · ${c.url}` : ""}`,
    })),
  ];
  return (
    <>
      <SelectField
        id="cfg-provider"
        label="Provider"
        value={provider}
        options={TOOL_PROVIDER_OPTIONS}
        onChange={(v) => set({ provider: v })}
      />
      {provider === "mcp" ? (
        <>
          <SelectField
            id="cfg-mcp-connector"
            label="Connector (from Settings)"
            value={connectorRef}
            options={connectorOptions}
            onChange={(v) => set({ mcp_connector_ref: v })}
          />
          {connectorRef ? (
            <p className="text-xs text-muted-foreground">
              Server + credentials resolve from your saved connector at run time.
            </p>
          ) : (
            <ManualMcpFields config={config} set={set} />
          )}
          <Field id="cfg-mcp-tool-filter" label="Tool filter (comma-separated, blank = all)">
            <Input
              id="cfg-mcp-tool-filter"
              data-testid="cfg-mcp-tool-filter"
              type="text"
              placeholder="e.g. search, fetch"
              value={toolFilter.join(", ")}
              onChange={(e) =>
                set({
                  mcp_tool_filter: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean),
                })
              }
            />
          </Field>
        </>
      ) : provider === "images_unsplash" ? (
        <>
          <MaxResultsField config={config} set={set} />
          <p className="text-xs text-muted-foreground">
            Add an Unsplash key in Settings → API Keys for live photos. Without one the tool
            returns placeholder results so the canvas still runs.
          </p>
        </>
      ) : provider === "generic_http" ? (
        <>
          <Field id="cfg-http-url" label="URL (GET)">
            <Input
              id="cfg-http-url"
              data-testid="cfg-http-url"
              type="url"
              placeholder="https://api.example.com/search"
              value={String(config.http_url ?? "")}
              onChange={(e) => set({ http_url: e.target.value })}
            />
          </Field>
          <Field id="cfg-http-params" label="Query params (k=v per line, {query} = the agent's input)">
            <Input
              id="cfg-http-params"
              data-testid="cfg-http-params"
              type="text"
              placeholder="q={query}, limit=5"
              value={Object.entries((config.http_params ?? {}) as Record<string, string>)
                .map(([k, v]) => `${k}=${v}`)
                .join(", ")}
              onChange={(e) =>
                set({
                  http_params: Object.fromEntries(
                    e.target.value
                      .split(",")
                      .map((pair) => pair.split("="))
                      .filter((kv) => kv.length === 2)
                      .map(([k, v]) => [k.trim(), v.trim()]),
                  ),
                })
              }
            />
          </Field>
          <Field id="cfg-jsonpath" label="Response path (dotted, blank = whole response)">
            <Input
              id="cfg-jsonpath"
              data-testid="cfg-jsonpath"
              type="text"
              placeholder="e.g. results.0.name"
              value={String(config.jsonpath ?? "")}
              onChange={(e) => set({ jsonpath: e.target.value })}
            />
          </Field>
        </>
      ) : (
        <>
          <Field id="cfg-api-key" label="API key">
            <Input
              id="cfg-api-key"
              data-testid="cfg-api-key"
              type="password"
              placeholder="runtime only — never written into generated code"
              value={String(config.api_key ?? "")}
              onChange={(e) => set({ api_key: e.target.value })}
            />
          </Field>
          <MaxResultsField config={config} set={set} />
        </>
      )}
    </>
  );
}

function MaxResultsField({ config, set }: { config: Config; set: Setter }) {
  return (
    <Field id="cfg-max-results" label="Max results">
      <Input
        id="cfg-max-results"
        type="number"
        min={1}
        value={Number(config.max_results ?? 3)}
        onChange={(e) => set({ max_results: Number(e.target.value) })}
      />
    </Field>
  );
}

function ManualMcpFields({ config, set }: { config: Config; set: Setter }) {
  return (
    <>
      <Field id="cfg-mcp-url" label="MCP server URL">
        <Input
          id="cfg-mcp-url"
          data-testid="cfg-mcp-url"
          type="url"
          placeholder="https://your-mcp-server/mcp"
          value={String(config.mcp_url ?? "")}
          onChange={(e) => set({ mcp_url: e.target.value })}
        />
      </Field>
      <SelectField
        id="cfg-mcp-transport"
        label="Transport"
        value={String(config.mcp_transport ?? "streamable_http")}
        options={MCP_TRANSPORT_OPTIONS}
        onChange={(v) => set({ mcp_transport: v })}
      />
      <Field id="cfg-mcp-token" label="Bearer token">
        <Input
          id="cfg-mcp-token"
          data-testid="cfg-mcp-token"
          type="password"
          placeholder="runtime only — never written into generated code"
          value={String(config.mcp_token ?? "")}
          onChange={(e) => set({ mcp_token: e.target.value })}
        />
      </Field>
    </>
  );
}

function RetrieverFields({ config, set }: { config: Config; set: Setter }) {
  const source = String(config.source ?? "demo");
  return (
    <>
      <SelectField
        id="cfg-source"
        label="Knowledge source"
        value={source}
        options={KNOWLEDGE_SOURCE_OPTIONS}
        onChange={(v) => set({ source: v })}
      />
      <Field id="cfg-top-k" label="Top K (chunks)">
        <Input
          id="cfg-top-k"
          data-testid="cfg-top-k"
          type="number"
          min={1}
          value={Number(config.top_k ?? 4)}
          onChange={(e) => set({ top_k: Number(e.target.value) })}
        />
      </Field>
      {source === "pgvector" ? (
        <>
          <Field id="cfg-collection" label="Collection (knowledge base)">
            <Input
              id="cfg-collection"
              data-testid="cfg-collection"
              placeholder="e.g. handbook"
              value={String(config.collection ?? "")}
              onChange={(e) => set({ collection: e.target.value })}
            />
          </Field>
          <Field id="cfg-embedding-model" label="Embedding model">
            <Input
              id="cfg-embedding-model"
              value={String(config.embedding_model ?? "text-embedding-3-small")}
              onChange={(e) => set({ embedding_model: e.target.value })}
            />
          </Field>
          <p className="text-xs text-muted-foreground">
            Code-gen only: the generated agent retrieves from your Postgres
            (<code>DATABASE_URL</code>) — never from Calypr.
          </p>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">
          A seeded in-memory demo KB — keyless and deterministic, so the canvas runs
          without a database. Switch to pgvector to point at your own data.
        </p>
      )}
    </>
  );
}

function PromptField({ config, set }: { config: Config; set: Setter }) {
  return (
    <Field id="cfg-prompt" label="System prompt (optional)">
      <Textarea
        id="cfg-prompt"
        data-testid="cfg-prompt"
        rows={3}
        value={String(config.system_prompt ?? "")}
        onChange={(e) => set({ system_prompt: e.target.value })}
      />
    </Field>
  );
}

function ResponderFields({ config, set }: { config: Config; set: Setter }) {
  return (
    <>
      <ModelField config={config} set={set} />
      <PromptField config={config} set={set} />
    </>
  );
}

function RevisorFields({ config, set }: { config: Config; set: Setter }) {
  return (
    <>
      <ModelField config={config} set={set} />
      <PromptField config={config} set={set} />
      <Field id="cfg-max-revisions" label="Max revisions">
        <Input
          id="cfg-max-revisions"
          data-testid="cfg-max-revisions"
          type="number"
          min={1}
          value={Number(config.max_revisions ?? 2)}
          onChange={(e) => set({ max_revisions: Number(e.target.value) })}
        />
      </Field>
    </>
  );
}

function ImageFields({ config, set }: { config: Config; set: Setter }) {
  const model = String(config.model ?? "gpt-image-2");
  return (
    <>
      <SelectField
        id="cfg-model"
        label="Image model"
        value={model}
        options={IMAGE_MODEL_OPTIONS}
        onChange={(v) => set({ model: v })}
      />
      <Field id="cfg-style" label="Style (applied to every prompt)">
        <Textarea
          id="cfg-style"
          data-testid="cfg-style"
          rows={2}
          placeholder="e.g. anime style illustration, vibrant colors, cel shading"
          value={String(config.style ?? "")}
          onChange={(e) => set({ style: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          A fixed look prepended to whatever the user asks — so “a dog” comes out in this style.
          Leave empty to use the prompt as-is; use <code>{"{prompt}"}</code> to place the user’s
          text yourself.
        </p>
      </Field>
      <SelectField
        id="cfg-size"
        label="Size"
        value={String(config.size ?? "1024x1024")}
        options={IMAGE_SIZE_OPTIONS}
        onChange={(v) => set({ size: v })}
      />
      <SelectField
        id="cfg-quality"
        label="Quality"
        value={String(config.quality ?? "auto")}
        options={IMAGE_QUALITY_OPTIONS}
        onChange={(v) => set({ quality: v })}
      />
      <Field id="cfg-n" label="Number of images">
        <Input
          id="cfg-n"
          data-testid="cfg-n"
          type="number"
          min={1}
          max={4}
          value={Number(config.n ?? 1)}
          onChange={(e) => set({ n: Number(e.target.value) })}
        />
      </Field>
      <p className="text-xs text-muted-foreground">
        Generates an image from the incoming prompt and shows it inline. The{" "}
        <code>fake</code> model is keyless (a tiny preview); gpt-image-* call OpenAI and are
        billed per run.
      </p>
    </>
  );
}

function TTSFields({ config, set }: { config: Config; set: Setter }) {
  const model = String(config.model ?? "gpt-4o-mini-tts");
  const instructable = model === "gpt-4o-mini-tts";
  return (
    <>
      <SelectField
        id="cfg-model"
        label="Voice model"
        value={model}
        options={TTS_MODEL_OPTIONS}
        onChange={(v) => set({ model: v })}
      />
      <SelectField
        id="cfg-voice"
        label="Voice"
        value={String(config.voice ?? "alloy")}
        options={TTS_VOICE_OPTIONS}
        onChange={(v) => set({ voice: v })}
      />
      {instructable ? (
        <Field id="cfg-instructions" label="Voice instructions (tone, pacing)">
          <Textarea
            id="cfg-instructions"
            data-testid="cfg-instructions"
            rows={2}
            placeholder="e.g. cheerful and upbeat, speaking quickly"
            value={String(config.instructions ?? "")}
            onChange={(e) => set({ instructions: e.target.value })}
          />
          <p className="text-xs text-muted-foreground">
            Steers how every line is read. Only gpt-4o-mini-tts supports this.
          </p>
        </Field>
      ) : (
        <Field id="cfg-speed" label="Speed">
          <Input
            id="cfg-speed"
            data-testid="cfg-speed"
            type="number"
            min={0.25}
            max={4}
            step={0.25}
            value={Number(config.speed ?? 1)}
            onChange={(e) => set({ speed: Number(e.target.value) })}
          />
        </Field>
      )}
      <p className="text-xs text-muted-foreground">
        Speaks the incoming text and shows an audio player. The <code>fake</code> model is keyless
        (a silent preview); the OpenAI voices call the API and are billed per run.
      </p>
    </>
  );
}

function UploadFields({ config, set }: { config: Config; set: Setter }) {
  return (
    <>
      <Field id="cfg-max-images" label="Max images per message">
        <Input
          id="cfg-max-images"
          data-testid="cfg-max-images"
          type="number"
          min={1}
          max={4}
          value={Number(config.max_images ?? 4)}
          onChange={(e) => set({ max_images: Number(e.target.value) })}
        />
      </Field>
      <p className="text-xs text-muted-foreground">
        Lets the user attach an image (≤5MB — label, receipt, screenshot) in the chat; a
        downstream Agent on a vision model (gpt-4o, gpt-4o-mini) reviews it. Without an
        attachment this block passes through unchanged.
      </p>
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
      {type === "tool" ? <ToolFields config={config} set={set} /> : null}
      {type === "retriever" ? <RetrieverFields config={config} set={set} /> : null}
      {type === "responder" ? <ResponderFields config={config} set={set} /> : null}
      {type === "revisor" ? <RevisorFields config={config} set={set} /> : null}
      {type === "router" ? <RouterFields config={config} set={set} /> : null}
      {type === "evaluator" ? <EvaluatorFields config={config} set={set} /> : null}
      {type === "memory" ? <MemoryFields config={config} set={set} /> : null}
      {type === "image" ? <ImageFields config={config} set={set} /> : null}
      {type === "tts" ? <TTSFields config={config} set={set} /> : null}
      {type === "upload" ? <UploadFields config={config} set={set} /> : null}

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
