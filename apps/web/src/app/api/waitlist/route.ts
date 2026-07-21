// Proxy landing-page waitlist signups to the API (server-side), mirroring /api/codegen.
const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.text();
  const r = await fetch(`${API_URL}/waitlist`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
  // 204 has no body; forward the status either way so the form can report failure.
  return new Response(r.status === 204 ? null : await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
