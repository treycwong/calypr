// Proxy connector delete to the Python API, forwarding the tenant identity.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ id: string }> };

export async function DELETE(_req: Request, { params }: Ctx) {
  const { id } = await params;
  const r = await fetch(`${API_URL}/connectors/${id}`, {
    method: "DELETE",
    headers: await internalHeaders(),
  });
  return new Response(null, { status: r.status });
}
