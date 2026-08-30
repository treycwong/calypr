// Proxy the flat-rate media price table from the Python API, forwarding the tenant identity.
// Served rather than mirrored in the canvas so the credit cost shown before a run is the same
// number the run is charged.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET() {
  const r = await fetch(`${API_URL}/media-prices`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
