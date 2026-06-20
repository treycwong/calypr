// Proxy graph validation/compile to the Python API (server-side).
const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.text();
  const r = await fetch(`${API_URL}/compile`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
