// Streaming proxy: forward the run request to the Python API and pipe its SSE stream
// straight back to the browser (same-origin, so no CORS; API URL stays server-side).
// /runs is public (anonymous playground), but we still forward the internal identity headers
// so a signed-in user's run is metered against their workspace. The API's run_workspace dep
// falls back to the shared dev workspace when they're absent, so anonymous runs still work.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const body = await req.text();
  const upstream = await fetch(`${API_URL}/runs`, {
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
