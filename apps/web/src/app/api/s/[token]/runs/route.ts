// Public share run proxy: forward an anonymous run to the Python API and pipe its SSE stream
// straight back. Copy of /api/runs MINUS internalHeaders() — share links are public by
// construction, so there is no identity to forward and nothing to 401 on.
const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

type Ctx = { params: Promise<{ token: string }> };

export async function POST(req: Request, { params }: Ctx) {
  const { token } = await params;
  const body = await req.text();
  const upstream = await fetch(`${API_URL}/share/${token}/runs`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body,
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
    },
  });
}
