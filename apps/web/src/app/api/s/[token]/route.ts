// Public share proxy: fetch the shared agent's NAME from the Python API. Anonymous by
// construction — no internalHeaders(): share links carry no identity, and the API endpoint has
// no workspace dependency. The response is name-only; the spec never crosses this boundary.
const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ token: string }> };

export async function GET(_req: Request, { params }: Ctx) {
  const { token } = await params;
  const r = await fetch(`${API_URL}/share/${token}`, { cache: "no-store" });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
