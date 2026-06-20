// Proxy agent create/list to the Python API (server-side).
const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

export async function POST(req: Request) {
  const body = await req.text();
  const r = await fetch(`${API_URL}/agents`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
  return json(await r.text(), r.status);
}

export async function GET() {
  const r = await fetch(`${API_URL}/agents`, { cache: "no-store" });
  return json(await r.text(), r.status);
}
