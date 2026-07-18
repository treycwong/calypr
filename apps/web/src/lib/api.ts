// Client helpers that talk to the same-origin Next route proxies (which forward to the
// Python API server-side — no CORS, API URL stays on the server).
import type { GraphSpec } from "@calypr/dsl";

export type RunEvent =
  | { type: "token"; text: string }
  | { type: "final"; output: string }
  | { type: "usage"; [k: string]: unknown }
  | { type: "error"; message: string };

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
  | { type: "error"; message: string; issues?: unknown[] };

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

export type WorkspaceInfo = { id: string; name: string };

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
export async function generateCode(graph: GraphSpec): Promise<string> {
  const res = await fetch("/api/codegen", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(graph),
  });
  if (!res.ok) throw new Error(`codegen failed (${res.status})`);
  return (await res.json()).code as string;
}
