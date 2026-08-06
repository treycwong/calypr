// Proxy the Playground's generated-media list to the Python API.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

export async function GET(req: Request) {
  const incoming = new URL(req.url).searchParams;
  const forwarded = new URLSearchParams();
  for (const key of ["q", "kind", "agent_id", "limit", "cursor"]) {
    const value = incoming.get(key);
    if (value) forwarded.set(key, value);
  }
  const qs = forwarded.toString();
  const r = await fetch(`${API_URL}/assets${qs ? `?${qs}` : ""}`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return json(await r.text(), r.status);
}
