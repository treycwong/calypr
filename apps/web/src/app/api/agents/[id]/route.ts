// Proxy a single agent (get / update / delete) to the Python API, forwarding the tenant identity.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

type Ctx = { params: Promise<{ id: string }> };

export async function GET(_req: Request, { params }: Ctx) {
  const { id } = await params;
  const r = await fetch(`${API_URL}/agents/${id}`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return json(await r.text(), r.status);
}

export async function PUT(req: Request, { params }: Ctx) {
  const { id } = await params;
  const body = await req.text();
  const r = await fetch(`${API_URL}/agents/${id}`, {
    method: "PUT",
    headers: { "content-type": "application/json", ...(await internalHeaders()) },
    body,
  });
  return json(await r.text(), r.status);
}

export async function DELETE(_req: Request, { params }: Ctx) {
  const { id } = await params;
  const r = await fetch(`${API_URL}/agents/${id}`, {
    method: "DELETE",
    headers: await internalHeaders(),
  });
  return new Response(null, { status: r.status });
}
