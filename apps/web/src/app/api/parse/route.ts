// Proxy edited Python -> GraphSpec to the API (server-side). The inverse of /api/codegen.
//
// Unlike /api/codegen this one is tenant-scoped: code export is a paid entitlement, so the API
// has to know whose workspace is asking (`require_code_export`). Without these headers a real
// deployment would 401 every parse, including a paying customer's. The 402 the API returns for
// an unentitled plan passes straight through to the client.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.text();
  const r = await fetch(`${API_URL}/parse`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await internalHeaders()) },
    body,
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
