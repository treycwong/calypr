// Client helpers that talk to the same-origin Next route proxies (which forward to the
// Python API server-side — no CORS, API URL stays on the server).
import type { GraphSpec } from "@calypr/dsl";

export type RunEvent =
  | { type: "token"; text: string }
  | { type: "node"; node_id: string; phase: "start" | "end" }
  | { type: "final"; output: string }
  | { type: "usage"; [k: string]: unknown }
  // A frontier model ran on the cheap platform model because no BYO key was on file. Always
  // surface this — the output is not from the model the user selected.
  | { type: "notice"; message: string }
  // `code` is a stable hint for the UI; "provider_key_rejected" gets a Fix it action.
  | { type: "error"; message: string; code?: string };

/** POST a JSON body to a same-origin SSE proxy and yield parsed `data:` events until the
 * stream ends (`[DONE]`). Shared by `runAgent` and `assistAgent`. */
async function* streamSSE<T>(
  url: string,
  body: unknown,
  httpError: (status: number) => T,
): AsyncGenerator<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    yield httpError(res.status);
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const line = frame.trim();
      if (!line.startsWith("data:")) continue;
      const data = line.slice(5).trim();
      if (data === "[DONE]") return;
      try {
        yield JSON.parse(data) as T;
      } catch {
        // ignore malformed frame
      }
    }
  }
}

/** Stream a run, yielding parsed SSE events until the stream closes. */
export async function* runAgent(
  graph: GraphSpec,
  message: string,
  threadId: string,
  images: string[] = [],
): AsyncGenerator<RunEvent> {
  yield* streamSSE<RunEvent>(
    "/api/runs",
    { graph, message, thread_id: threadId, images },
    (status) => ({ type: "error", message: `run failed (${status})` }),
  );
}

/** Stream a run against a share link — spec-free: the graph lives server-side behind the token.
 * Mirrors `runAgent`, but the anonymous `/api/s/{token}/runs` proxy forwards no identity. */
export async function* runShare(
  token: string,
  message: string,
  threadId: string,
  images: string[] = [],
): AsyncGenerator<RunEvent> {
  yield* streamSSE<RunEvent>(
    `/api/s/${token}/runs`,
    { message, thread_id: threadId, images },
    (status) => ({ type: "error", message: `run failed (${status})` }),
  );
}

/** Client-side pre-checks for an image attachment (the API re-enforces both server-side). */
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // 5MB
export const UPLOAD_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/gif"];

/** Upload an image for a vision run; returns its public blob URL. POSTs the raw file body —
 * the proxy forwards it and the API enforces the 5MB cap + type/magic checks. */
async function uploadTo(url: string, file: File): Promise<string> {
  if (!UPLOAD_IMAGE_TYPES.includes(file.type)) {
    throw new Error("Only PNG, JPEG, WebP, or GIF images are supported.");
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error("Images must be 5MB or smaller.");
  }
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": file.type },
    body: file,
  });
  if (!res.ok) {
    const detail = await res.json().then((j) => j.detail).catch(() => null);
    throw new Error(typeof detail === "string" ? detail : `upload failed (${res.status})`);
  }
  return (await res.json()).url as string;
}

export const uploadImage = (file: File) => uploadTo("/api/uploads", file);
export const uploadShareImage = (token: string, file: File) =>
  uploadTo(`/api/s/${token}/uploads`, file);

/** A minted share link (mirror of the API's `ShareInfo`). */
export type ShareInfo = {
  token: string;
  run_cap: number | null;
  run_count: number;
  created_at: string;
  revoked_at: string | null;
};

/** Mint a share link for a saved agent. `runCap` omitted ⇒ the API's default cap. */
export async function createShare(agentId: string, runCap?: number): Promise<ShareInfo> {
  const res = await fetch(`/api/agents/${agentId}/share`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(runCap != null ? { run_cap: runCap } : {}),
  });
  if (!res.ok) throw new Error(`share failed (${res.status})`);
  return res.json();
}

/** One chat turn sent to the assistant. */
export type AssistMessageInput = { role: "user" | "assistant"; content: string };

/** Events the assistant streams while drafting a graph (mirror of `calypr_assistant`). */
export type AssistEvent =
  | { type: "status"; phase: "drafting" | "validating" | "repairing" }
  | { type: "note"; text: string }
  | { type: "graph"; spec: GraphSpec }
  | { type: "usage"; input_tokens: number; output_tokens: number; model: string }
  // The chosen model needed a BYO key that isn't on file, so the draft ran on the fallback.
  | { type: "notice"; message: string }
  | { type: "error"; message: string; code?: string; issues?: unknown[] };

/** Ask the assistant to draft/refine a graph from natural language, streaming events. */
export async function* assistAgent(
  messages: AssistMessageInput[],
  currentGraph: GraphSpec | null,
  model?: string,
): AsyncGenerator<AssistEvent> {
  yield* streamSSE<AssistEvent>(
    "/api/assist",
    { messages, current_graph: currentGraph, model },
    (status) => ({ type: "error", message: `assistant unavailable (${status})` }),
  );
}

/** A saved agent ("project") with its full graph. */
export type AgentDetail = { id: string; name: string; graph: GraphSpec };

/** Create a new saved agent; returns it (with the new id). */
export async function createAgent(name: string, graph: GraphSpec): Promise<AgentDetail> {
  const res = await fetch("/api/agents", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, graph }),
  });
  if (!res.ok) throw new Error(`save failed (${res.status})`);
  return res.json();
}

/** Update an existing saved agent in place (name and/or graph) — no duplicate rows. */
export async function updateAgent(
  id: string,
  body: { name?: string; graph?: GraphSpec },
): Promise<AgentDetail> {
  const res = await fetch(`/api/agents/${id}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`save failed (${res.status})`);
  return res.json();
}

/** Load a saved agent by id (to reopen it on the canvas). */
export async function getAgent(id: string): Promise<AgentDetail> {
  const res = await fetch(`/api/agents/${id}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`load failed (${res.status})`);
  return res.json();
}

/** A saved agent in the dashboard list (no graph). */
export type AgentSummary = { id: string; name: string; updated_at: string };

/** The current user's saved agents ("projects"), most-recently-edited first. */
export async function listAgents(): Promise<AgentSummary[]> {
  const res = await fetch("/api/agents", { cache: "no-store" });
  if (!res.ok) throw new Error(`list failed (${res.status})`);
  return res.json();
}

/** Delete a saved agent. */
export async function deleteAgent(id: string): Promise<void> {
  const res = await fetch(`/api/agents/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`delete failed (${res.status})`);
}

/** A saved MCP/OAuth connector (never carries the secret — only `has_secret`). */
export type Connector = {
  id: string;
  kind: "mcp" | "notion";
  name: string;
  url: string | null;
  transport: string;
  has_secret: boolean;
  meta: Record<string, unknown>;
  created_at: string;
};

/** The workspace's saved connectors (Settings panel + the Tool node's connector dropdown). */
export async function listConnectors(): Promise<Connector[]> {
  const res = await fetch("/api/connectors", { cache: "no-store" });
  if (!res.ok) throw new Error(`list connectors failed (${res.status})`);
  return res.json();
}

/** Save a Tier B MCP server (URL + optional bearer, stored encrypted server-side). */
export async function createConnector(body: {
  name: string;
  url: string;
  transport?: string;
  secret?: string;
}): Promise<Connector> {
  const res = await fetch("/api/connectors", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`save connector failed (${res.status})`);
  return res.json();
}

/** Delete a connector. */
export async function deleteConnector(id: string): Promise<void> {
  const res = await fetch(`/api/connectors/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`delete failed (${res.status})`);
}

/** Result of a live ListTools probe against a connector. */
export type ConnectorTest = { ok: boolean; tools: string[]; error: string | null };

/** Test a connector — resolves it server-side and lists its tools. */
export async function testConnector(id: string): Promise<ConnectorTest> {
  const res = await fetch(`/api/connectors/${id}/test`, { method: "POST" });
  if (!res.ok) throw new Error(`test failed (${res.status})`);
  return res.json();
}

/** Start the Notion OAuth flow — returns the URL to open in the browser. */
export async function notionConnectUrl(): Promise<string> {
  const res = await fetch("/api/connectors/notion/connect", { cache: "no-store" });
  if (!res.ok) {
    const detail = res.status === 501 ? " (Notion is not configured on this server)" : "";
    throw new Error(`could not start Notion connect${detail}`);
  }
  return (await res.json()).authorize_url as string;
}

/** A model provider's BYO-key state ({has_key}) — the value is never returned. */
export type ProviderKeyInfo = { provider: string; has_key: boolean };

/** Which providers have a workspace BYO key on file (the Settings "API Keys" section). */
export async function listProviderKeys(): Promise<ProviderKeyInfo[]> {
  const res = await fetch("/api/provider-keys", { cache: "no-store" });
  if (!res.ok) throw new Error(`list provider keys failed (${res.status})`);
  return res.json();
}

/** Set/replace a provider's BYO key (stored encrypted server-side). */
export async function setProviderKey(provider: string, key: string): Promise<void> {
  const res = await fetch(`/api/provider-keys/${provider}`, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ key }),
  });
  if (!res.ok) throw new Error(`save key failed (${res.status})`);
}

/** Remove a provider's BYO key (runs fall back to the server key). */
export async function deleteProviderKey(provider: string): Promise<void> {
  const res = await fetch(`/api/provider-keys/${provider}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`delete key failed (${res.status})`);
}

/** `plan` is the entitlement tier (`free|beta|plus`) the client gates optional features on. */
export type WorkspaceInfo = {
  id: string;
  name: string;
  plan: string;
  /** The email the API sees us as — shown when a beta-gated feature is locked. */
  signed_in_as?: string | null;
  /** The workspace's AI-assistant model; "" means inherit the server default. */
  assistant_model?: string;
};

/** A choice in the Settings assistant-model picker. `byo_provider` set ⇒ frontier: usable only
 * once that provider's key is saved in API Keys. Served by the API so the picker and the
 * validation on save can never drift apart. */
export type AssistantModelOption = {
  value: string;
  label: string;
  byo_provider: string | null;
};

/** A BYO-key provider row in Settings. `status` is the backend's honest state: "available"
 * means a key can be saved and will actually be used; "coming_soon" means the input is
 * disabled because nothing would read the key yet. */
export type LLMProvider = {
  provider: string;
  label: string;
  model_label: string;
  status: "available" | "coming_soon";
  note: string;
};

/** The provider list shown in Settings → Workspace. */
export async function listLLMProviders(): Promise<LLMProvider[]> {
  const res = await fetch("/api/llm-providers", { cache: "no-store" });
  if (!res.ok) throw new Error(`llm providers failed (${res.status})`);
  return res.json();
}

/** The models the AI assistant may be pointed at. */
export async function listAssistantModels(): Promise<AssistantModelOption[]> {
  const res = await fetch("/api/assistant-models", { cache: "no-store" });
  if (!res.ok) throw new Error(`assistant models failed (${res.status})`);
  return res.json();
}

/** Set the workspace's default AI-assistant model ("" = server default). */
export async function setAssistantModel(model: string): Promise<WorkspaceInfo> {
  const res = await fetch("/api/workspace", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ assistant_model: model }),
  });
  if (!res.ok) throw new Error(`save assistant model failed (${res.status})`);
  return res.json();
}

/** Landing-page waitlist signup. Idempotent server-side, so a double submit is harmless. */
export async function joinWaitlist(email: string, source = "landing"): Promise<void> {
  const res = await fetch("/api/waitlist", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, source }),
  });
  if (!res.ok) throw new Error(`waitlist failed (${res.status})`);
}

/** The current user's workspace. */
export async function getWorkspace(): Promise<WorkspaceInfo> {
  const res = await fetch("/api/workspace", { cache: "no-store" });
  if (!res.ok) throw new Error(`workspace failed (${res.status})`);
  return res.json();
}

/** Rename the current workspace. */
export async function renameWorkspace(name: string): Promise<WorkspaceInfo> {
  const res = await fetch("/api/workspace", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(`rename failed (${res.status})`);
  return res.json();
}

export type Template = {
  id: string;
  name: string;
  description: string;
  kind: "framework" | "template";
  graph: GraphSpec;
};

/** The canvas starter gallery: frameworks (agent patterns) + templates (use cases). */
export async function listTemplates(): Promise<Template[]> {
  const res = await fetch("/api/templates", { cache: "no-store" });
  if (!res.ok) throw new Error(`templates failed (${res.status})`);
  return res.json();
}

/** The 'code' altitude: get the agent as ownable Python (LangGraph). */
export type GeneratedCode = {
  code: string;
  /** The server sent only the opening lines — this workspace isn't entitled to the full file. */
  truncated: boolean;
  /** Lines in the full file, so a preview can say how much is behind the upgrade. */
  totalLines: number | null;
};

export async function generateCode(graph: GraphSpec): Promise<GeneratedCode> {
  const res = await fetch("/api/codegen", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(graph),
  });
  if (!res.ok) throw new Error(`codegen failed (${res.status})`);
  const body = await res.json();
  return {
    code: body.code as string,
    truncated: Boolean(body.truncated),
    totalLines: (body.total_lines as number | null) ?? null,
  };
}

export type ParseResult = {
  graph: GraphSpec;
  /** Advisory notes (a missing metadata trailer, a statement the walker skipped). */
  warnings: string[];
  /** Node ids that fell back to a Custom Code node because no recogniser matched. */
  degraded_nodes: string[];
};

/**
 * The reverse round-trip: edited Python back to a graph the canvas can render.
 *
 * The server never fails on unparseable input — it degrades what it can't recognise and says so
 * — so a non-OK response here means the request itself failed, not that the code was bad.
 *
 * 402 is the one a user can actually hit: code export is a paid entitlement, so a plan that
 * doesn't include it gets told that instead of a bare status code. The UI normally hides the
 * button in that case (`roundtripEnabled`), so this fires when the two disagree — a plan that
 * changed mid-session, or a hand-rolled request.
 */
export async function parseCode(code: string): Promise<ParseResult> {
  const res = await fetch("/api/parse", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (res.status === 402) {
    throw new Error("Code export is a Plus feature — upgrade to apply edits to the canvas.");
  }
  if (!res.ok) throw new Error(`parse failed (${res.status})`);
  return (await res.json()) as ParseResult;
}
