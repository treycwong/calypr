// Client helpers that talk to the same-origin Next route proxies (which forward to the
// Python API server-side — no CORS, API URL stays on the server).
import type { GraphSpec } from "@calypr/dsl";

export type RunEvent =
  | { type: "token"; text: string }
  | { type: "final"; output: string }
  | { type: "usage"; [k: string]: unknown }
  | { type: "error"; message: string };

/** Stream a run, yielding parsed SSE events until the stream closes. */
export async function* runAgent(
  graph: GraphSpec,
  message: string,
  threadId: string,
): AsyncGenerator<RunEvent> {
  const res = await fetch("/api/runs", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ graph, message, thread_id: threadId }),
  });
  if (!res.ok || !res.body) {
    yield { type: "error", message: `run failed (${res.status})` };
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
        yield JSON.parse(data) as RunEvent;
      } catch {
        // ignore malformed frame
      }
    }
  }
}

export async function saveAgent(name: string, graph: GraphSpec): Promise<{ id: string }> {
  const res = await fetch("/api/agents", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, graph }),
  });
  if (!res.ok) throw new Error(`save failed (${res.status})`);
  return res.json();
}

export type Template = {
  id: string;
  name: string;
  description: string;
  graph: GraphSpec;
};

/** The archetype starter graphs (the agent ladder), simple→complex. */
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
