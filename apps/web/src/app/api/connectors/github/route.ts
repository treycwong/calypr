// Proxy GitHub connector creation to the Python API (server-side), forwarding the tenant
// identity. Separate from the Tier B `/api/connectors` route because the body is a token + scope
// rather than a URL, and because the PAT must never be handled by anything but this hop.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.text();
  const r = await fetch(`${API_URL}/connectors/github`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await internalHeaders()) },
    body,
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
