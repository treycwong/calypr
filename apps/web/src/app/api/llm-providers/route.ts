// Proxy the LLM provider catalogue from the Python API, forwarding the tenant identity.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET() {
  const r = await fetch(`${API_URL}/llm-providers`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
