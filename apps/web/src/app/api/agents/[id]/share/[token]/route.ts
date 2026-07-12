// Authenticated share revoke: DELETE a saved agent's share link. Owner-only — forwards the
// tenant identity like the other /api/agents proxies.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ id: string; token: string }> };

export async function DELETE(_req: Request, { params }: Ctx) {
  const { id, token } = await params;
  const r = await fetch(`${API_URL}/agents/${id}/share/${token}`, {
    method: "DELETE",
    headers: await internalHeaders(),
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
