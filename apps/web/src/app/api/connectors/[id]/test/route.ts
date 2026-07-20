// Proxy the connector live-test (ListTools probe) to the Python API.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

type Ctx = { params: Promise<{ id: string }> };

export async function POST(_req: Request, { params }: Ctx) {
  const { id } = await params;
  const r = await fetch(`${API_URL}/connectors/${id}/test`, {
    method: "POST",
    headers: await internalHeaders(),
  });
  return json(await r.text(), r.status);
}
