// Public share upload proxy: forward the raw image body to the Python API's token-gated
// upload endpoint. Copy of /api/uploads MINUS internalHeaders() — share links are public by
// construction; the API 404s unknown/revoked tokens and enforces the 5MB/type/magic gates.
const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ token: string }> };

export async function POST(req: Request, { params }: Ctx) {
  const { token } = await params;
  const upstream = await fetch(`${API_URL}/share/${token}/uploads`, {
    method: "POST",
    headers: {
      "content-type": req.headers.get("content-type") ?? "application/octet-stream",
    },
    body: await req.arrayBuffer(),
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
