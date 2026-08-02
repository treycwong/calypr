// Delete a workspace. Ownership is checked by the API against the caller's account.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const r = await fetch(`${API_URL}/workspaces/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: await internalHeaders(),
  });
  if (r.status === 204) return new Response(null, { status: 204 });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
