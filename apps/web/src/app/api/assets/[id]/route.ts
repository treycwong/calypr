// Proxy deleting one generated file to the Python API. The API removes the blob object too.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ id: string }> };

export async function DELETE(_req: Request, { params }: Ctx) {
  const { id } = await params;
  const r = await fetch(`${API_URL}/assets/${id}`, {
    method: "DELETE",
    headers: await internalHeaders(),
  });
  return new Response(null, { status: r.status });
}
