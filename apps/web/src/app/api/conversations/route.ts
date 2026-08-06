// Proxy the Playground's conversation list to the Python API, forwarding the tenant identity.
//
// The search term rides through as `q` rather than being applied here: the browser holds only
// the page it is looking at, so filtering client-side would search whatever happened to be
// loaded and quietly miss the rest.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

export async function GET(req: Request) {
  const incoming = new URL(req.url).searchParams;
  // Allowlisted rather than forwarded wholesale — an unexpected parameter should be dropped at
  // the proxy, not handed to the API to interpret.
  const forwarded = new URLSearchParams();
  for (const key of ["q", "agent_id", "limit", "cursor"]) {
    const value = incoming.get(key);
    if (value) forwarded.set(key, value);
  }
  const qs = forwarded.toString();
  const r = await fetch(`${API_URL}/conversations${qs ? `?${qs}` : ""}`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return json(await r.text(), r.status);
}
