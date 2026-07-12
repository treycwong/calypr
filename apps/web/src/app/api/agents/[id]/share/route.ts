// Authenticated share management: mint (POST) and list (GET) a saved agent's share links.
// Forwards the tenant identity like the other /api/agents proxies — these are owner-only.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

type Ctx = { params: Promise<{ id: string }> };

export async function POST(req: Request, { params }: Ctx) {
  const { id } = await params;
  const body = await req.text();
  const r = await fetch(`${API_URL}/agents/${id}/share`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await internalHeaders()) },
    body,
  });
  return json(await r.text(), r.status);
}

export async function GET(_req: Request, { params }: Ctx) {
  const { id } = await params;
  const r = await fetch(`${API_URL}/agents/${id}/shares`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return json(await r.text(), r.status);
}
