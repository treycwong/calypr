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
  // A media node durably stored a generated file. Carries the same payload the `asset` row is
  // built from; the Playground uses it only as a signal that the Media tab is now stale.
  | { type: "asset"; [k: string]: unknown }
  // The durable conversation this turn was recorded against, so the History tab can highlight
  // the active row without a fetch. Absent when history is disabled (no database).
  | { type: "conversation"; conversation_id: string; thread_id: string }
  // `code` is a stable hint for the UI; "provider_key_rejected" gets a Fix it action.
  | { type: "error"; message: string; code?: string }
  // Share links only, and always first. Anonymous visitors all share one public token, so the
  // conversation id is the only thing separating two strangers — which makes it a credential.
  // The server therefore mints it rather than trusting one from the browser, and the client
  // echoes this value back to continue the conversation.
  | { type: "thread"; thread_id: string };

/** POST a JSON body to a same-origin SSE proxy and yield parsed `data:` events until the
 * stream ends (`[DONE]`). Shared by `runAgent` and `assistAgent`. */
async function* streamSSE<T>(
  url: string,
  body: unknown,
  httpError: (status: number) => T,
  signal?: AbortSignal,
): AsyncGenerator<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
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
  /** The saved project this run belongs to, when there is one. Without it every playground run
   *  records `agent_id = NULL` and neither run history nor the History tab can say which
   *  project a conversation came from. */
  agentId?: string,
  /** Aborted when the Playground unmounts or the user starts a new chat. Without it a closed
   *  panel leaves the request running until the abandoned generator is finalized, and the
   *  server records the half-written answer as an error rather than as a partial. */
  signal?: AbortSignal,
): AsyncGenerator<RunEvent> {
  yield* streamSSE<RunEvent>(
    "/api/runs",
    { graph, message, thread_id: threadId, images, agent_id: agentId },
    (status) => ({ type: "error", message: `run failed (${status})` }),
    signal,
  );
}

/** Stream a run against a share link — spec-free: the graph lives server-side behind the token.
 * Mirrors `runAgent`, but the anonymous `/api/s/{token}/runs` proxy forwards no identity. */
export async function* runShare(
  token: string,
  message: string,
  /** Omitted on the first turn — the server mints it and returns it as a `thread` event. */
  threadId: string | undefined,
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
  // A plan cap is an answer, not a failure. The API has always sent the reason, the limit and
  // what's used; this used to throw `save failed (402)` and drop all of it on the floor, at the
  // exact moment someone was trying to start work.
  if (res.status === 402) {
    const detail = (await res.json().catch(() => ({}))).detail ?? {};
    throw new CapReachedError(
      detail.reason ?? "project_cap",
      detail.message ?? "You've reached your plan's project limit.",
      detail.limit,
      detail.used,
    );
  }
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
export type AgentSummary = {
  id: string;
  name: string;
  updated_at: string;
  /** Beyond the plan's project cap, or inside a locked workspace. Read-only either way. */
  locked?: boolean;
};

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
  kind: "mcp" | "notion" | "github";
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

/** The GitHub toolsets a connector can be scoped to ("" = GitHub's own default set). */
export const GITHUB_TOOLSETS = ["", "repos", "issues", "pull_requests", "actions", "all"] as const;

/** Save a GitHub connector from a personal access token.
 *
 * The token goes straight to the API and is encrypted there — it is never stored in the browser
 * and never comes back on any response. `readonly` defaults to true at both ends. */
export async function createGithubConnector(body: {
  name?: string;
  pat: string;
  toolset?: string;
  readonly?: boolean;
}): Promise<Connector> {
  const res = await fetch("/api/connectors/github", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`save GitHub connector failed (${res.status})`);
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
/** `key_hint` is the key's last 4 characters, stored in the clear at write time so the UI can say
 *  *which* key is on file without the real one ever leaving the server. `null` means no key, or a
 *  key saved before migration `0020`. */
export type ProviderKeyInfo = {
  provider: string;
  has_key: boolean;
  key_hint?: string | null;
};

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
  /** The model canvas LLM nodes inherit; "" means the platform default (gpt-4o-mini). */
  default_model?: string;
  /** This cycle's credit allowance and what's left, in whole credits. */
  credits?: { allowance: number; remaining: number; used: number };
  /** What the plan allows. Served by the API so the UI can render "3 of 20" without hard-coding
   * the 20 and drifting from what is actually enforced. */
  limits?: PlanLimits;
  /** What's been used against those caps, pooled across the account's workspaces. */
  usage?: AccountUsage;
};

/** Plan caps. `storage_bytes` is displayed, not enforced — see `storage_usage.py` for why. */
export type PlanLimits = {
  projects: number;
  workspaces: number;
  monthly_credits: number;
  storage_bytes: number;
};

/** Usage against `PlanLimits`, pooled per account.
 *
 * `storage_measured_at` is null until the nightly job has run: storage is measured on a
 * schedule, so the UI says when rather than implying the number is live. */
export type AccountUsage = {
  projects: number;
  workspaces: number;
  storage_bytes: number;
  storage_measured_at?: string | null;
};

/** One row in the workspace switcher. */
export type WorkspaceSummary = {
  id: string;
  name: string;
  created_at?: string | null;
  is_current: boolean;
  /** Beyond the plan's cap after a downgrade: readable and deletable, but read-only. */
  locked?: boolean;
};

/** The switcher's payload. `can_create` is decided by the API from `entitlements.LIMITS` — the
 *  same table `create_workspace` enforces — so the UI never re-derives "free means one" here. */
export type WorkspaceList = {
  workspaces: WorkspaceSummary[];
  plan: string;
  can_create: boolean;
  /** Whether creating another project would be allowed. Answered by the API from the same
   *  predicate that enforces the cap — never derived here from a plan name and a row count. */
  can_create_project: boolean;
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

/** The model every LLM block inherits unless it names one itself. "" = platform default. */
export async function setDefaultModel(model: string): Promise<WorkspaceInfo> {
  const res = await fetch("/api/workspace", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ default_model: model }),
  });
  if (!res.ok) throw new Error(`save default model failed (${res.status})`);
  return res.json();
}

/** Start a Stripe Checkout Session and return where to send the browser.
 *
 * `null` means billing isn't switched on yet (the API 503s without Stripe keys) — the caller
 * falls back to capturing intent rather than showing an error, because "we can't take your
 * money yet" is not the user's failure. */
export async function startCheckout(): Promise<string | null> {
  const res = await fetch("/api/billing/checkout", { method: "POST" });
  if (res.status === 503) return null;
  if (!res.ok) throw new Error(`checkout failed (${res.status})`);
  return (await res.json()).url as string;
}

/** What the Billing tab renders: the plan, when the current paid period ends (renewal date, or
 * cutoff once a cancel is pending), and whether "Manage billing" can open the Stripe portal. */
export type SubscriptionInfo = {
  plan: string;
  /** ISO 8601, or null for a workspace that has never subscribed. */
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  /** True only once there's a Stripe customer to manage and billing is switched on. */
  portal_available: boolean;
};

/** The workspace's subscription state for the Billing tab. Reads mirrored columns server-side,
 * so it never blocks on Stripe. */
export async function getSubscription(): Promise<SubscriptionInfo> {
  const res = await fetch("/api/billing/subscription", { cache: "no-store" });
  if (!res.ok) throw new Error(`subscription failed (${res.status})`);
  return res.json();
}

/** Open Stripe's hosted Customer Portal (cancel / plan change / payment method / invoices) and
 * return where to send the browser. `null` means billing isn't switched on (503); the caller
 * shouldn't have offered the button in that case, but degrades quietly if it did. */
export async function startBillingPortal(): Promise<string | null> {
  const res = await fetch("/api/billing/portal", { method: "POST" });
  if (res.status === 503) return null;
  if (!res.ok) throw new Error(`billing portal failed (${res.status})`);
  return (await res.json()).url as string;
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

/** Every workspace on this account — the switcher's list. */
export async function listWorkspaces(): Promise<WorkspaceList> {
  const res = await fetch("/api/workspaces", { cache: "no-store" });
  if (!res.ok) throw new Error(`workspaces failed (${res.status})`);
  return res.json();
}

/** Raised when a plan cap refuses an action, carrying the API's message so the UI can show
 * what the user actually ran out of rather than a generic failure. */
export class CapReachedError extends Error {
  constructor(
    readonly reason: string,
    message: string,
    readonly limit?: number,
    /** How many are already in use, pooled across the account's workspaces. */
    readonly used?: number,
  ) {
    super(message);
    this.name = "CapReachedError";
  }
}

/** Create a workspace. Throws `CapReachedError` when the plan's workspace cap is reached. */
export async function createWorkspace(name: string): Promise<WorkspaceInfo> {
  const res = await fetch("/api/workspaces", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (res.status === 402) {
    const detail = (await res.json().catch(() => ({}))).detail ?? {};
    throw new CapReachedError(
      detail.reason ?? "workspace_cap",
      detail.message ?? "You've reached your plan's workspace limit.",
      detail.limit,
    );
  }
  if (!res.ok) throw new Error(`create workspace failed (${res.status})`);
  return res.json();
}

/** Delete a workspace and everything in it. The API refuses the last one. */
export async function deleteWorkspace(id: string): Promise<void> {
  const res = await fetch(`/api/workspaces/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    const detail = (await res.json().catch(() => ({}))).detail;
    throw new Error(typeof detail === "string" ? detail : `delete failed (${res.status})`);
  }
}

/** Remember which workspace is open. A cookie the API validates — see `workspace/switch`.
 * Pass no id to clear it (sign-out). Callers should `router.refresh()` afterwards: the dashboard
 * shell is a server component that reads this cookie. */
export async function switchWorkspace(id?: string): Promise<void> {
  const res = await fetch("/api/workspace/switch", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ workspace_id: id ?? "" }),
  });
  if (!res.ok && res.status !== 204) throw new Error(`switch failed (${res.status})`);
}

/** Credits, projects, workspaces and storage against the caps — the Usage tab. */
export async function getUsage(): Promise<WorkspaceInfo> {
  const res = await fetch("/api/usage", { cache: "no-store" });
  if (!res.ok) throw new Error(`usage failed (${res.status})`);
  return res.json();
}

export type Template = {
  id: string;
  name: string;
  description: string;
  kind: "framework" | "template";
  /** Gallery grouping for the Workflows page. Empty for frameworks, which aren't listed there. */
  category: string;
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

export type AccountDeleted = { deleted: boolean; mode: "live" | "dev" };

/**
 * Delete the whole account — every workspace, the subscription, the login.
 *
 * The error message is surfaced verbatim rather than flattened to a status code, because the
 * one a user can actually hit is the Stripe 502: *nothing* was deleted and retrying is the
 * right move, which a bare "delete failed (502)" would not tell them.
 */
export async function deleteAccount(): Promise<AccountDeleted> {
  const res = await fetch("/api/account", { method: "DELETE" });
  if (!res.ok) {
    const detail = await res
      .json()
      .then((b) => (typeof b?.detail === "string" ? b.detail : ""))
      .catch(() => "");
    throw new Error(detail || `Couldn't delete your account (${res.status}). Please try again.`);
  }
  return (await res.json()) as AccountDeleted;
}

/* -------------------------------------------------------------- conversations + media */

export type ConversationSummary = {
  id: string;
  title: string;
  /** The thread suffix — send it back as `threadId` to resume the conversation. */
  thread_id: string;
  agent_id: string | null;
  message_count: number;
  /** False once the agent's memory (the LangGraph checkpoint) has aged out. The transcript is
   *  still fully readable; the agent just no longer remembers it. */
  has_state: boolean;
  preview: string;
  created_at: string | null;
  updated_at: string | null;
};

export type StoredMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  images: string[];
  /** `partial` when the user stopped the run mid-answer, `errored` when it failed. */
  status: "complete" | "partial" | "errored";
  created_at: string | null;
};

export type ConversationDetail = ConversationSummary & {
  messages: StoredMessage[];
  truncated: boolean;
};

export type StoredAsset = {
  id: string;
  kind: "image" | "audio";
  url: string;
  caption: string;
  content_type: string | null;
  bytes: number;
  model: string | null;
  conversation_id: string | null;
  created_at: string | null;
};

type Page<T> = { items: T[]; next_cursor: string | null };

async function getJSON<T>(url: string, fallback: T): Promise<T> {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) return fallback;
  return (await r.json()) as T;
}

const query = (params: Record<string, string | number | undefined>) => {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
};

/** Past Playground conversations, newest first. `q` searches titles *and* message bodies
 *  server-side — the browser only holds the page it is showing. */
export function listConversations(opts: {
  q?: string;
  agentId?: string;
  limit?: number;
  cursor?: string;
} = {}): Promise<Page<ConversationSummary>> {
  const url = `/api/conversations${query({
    q: opts.q,
    agent_id: opts.agentId,
    limit: opts.limit,
    cursor: opts.cursor,
  })}`;
  return getJSON<Page<ConversationSummary>>(url, { items: [], next_cursor: null });
}

/** One conversation with its transcript. Null when it no longer exists. */
export async function getConversation(id: string): Promise<ConversationDetail | null> {
  const r = await fetch(`/api/conversations/${id}`, { cache: "no-store" });
  if (!r.ok) return null;
  return (await r.json()) as ConversationDetail;
}

export async function renameConversation(id: string, title: string): Promise<boolean> {
  const r = await fetch(`/api/conversations/${id}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title }),
  });
  return r.ok;
}

/** Deletes the transcript, the agent's memory of it, **and the media it generated**. */
export async function deleteConversation(id: string): Promise<boolean> {
  const r = await fetch(`/api/conversations/${id}`, { method: "DELETE" });
  return r.ok;
}

export function listAssets(opts: {
  q?: string;
  kind?: string;
  agentId?: string;
  limit?: number;
  cursor?: string;
} = {}): Promise<Page<StoredAsset>> {
  const url = `/api/assets${query({
    q: opts.q,
    kind: opts.kind,
    agent_id: opts.agentId,
    limit: opts.limit,
    cursor: opts.cursor,
  })}`;
  return getJSON<Page<StoredAsset>>(url, { items: [], next_cursor: null });
}

export async function deleteAsset(id: string): Promise<boolean> {
  const r = await fetch(`/api/assets/${id}`, { method: "DELETE" });
  return r.ok;
}
