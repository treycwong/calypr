// Streaming proxy: forward the assist request to the Python API and pipe its SSE stream
// straight back to the browser (same-origin, so no CORS; API URL stays server-side).
// Unlike /api/runs, /assist is tenant-scoped, so it forwards the internal identity headers
// (a no-op locally where CALYPR_INTERNAL_KEY is unset).
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.text();
  const upstream = await fetch(`${API_URL}/assist`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await internalHeaders()) },
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
