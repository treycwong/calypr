// Proxy graph -> Python codegen to the API (server-side).
//
// Tenant-scoped, because how much of the file comes back depends on the plan: an entitled
// workspace gets all of it, everyone else gets a preview plus `truncated: true`. Signed-out
// callers legitimately have no user id — the API reads that as "preview", not as an error.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.text();
  const r = await fetch(`${API_URL}/codegen`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await internalHeaders()) },
    body,
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
