// Upload proxy: forward the raw image body to the Python API (which enforces the 5MB cap,
// content-type allowlist, and magic-byte sniff) and return its JSON {url}. Identity headers
// forwarded like /api/runs so uploads attribute to the signed-in workspace when present.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const upstream = await fetch(`${API_URL}/uploads`, {
    method: "POST",
    headers: {
      "content-type": req.headers.get("content-type") ?? "application/octet-stream",
      ...(await internalHeaders()),
    },
    body: await req.arrayBuffer(),
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
