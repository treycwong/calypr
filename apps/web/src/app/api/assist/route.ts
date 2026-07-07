// Streaming proxy: forward the assist request to the Python API and pipe its SSE stream
// straight back to the browser (same-origin, so no CORS; API URL stays server-side).
// Mirrors app/api/runs/route.ts.
const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.text();
  const upstream = await fetch(`${API_URL}/assist`, {
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
