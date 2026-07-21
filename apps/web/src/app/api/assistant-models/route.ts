// Proxy the assistant-model allow-list from the Python API, forwarding the tenant identity.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET() {
  const r = await fetch(`${API_URL}/assistant-models`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
