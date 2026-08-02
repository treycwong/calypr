// Nightly maintenance, driven by Vercel cron (see `vercel.json`).
//
// The scheduler lives here rather than next to the API because the API runs on Railway, which
// has no cron — and standing up a second scheduler to operate is worse than one proxy route.
// Vercel signs its cron invocations with `CRON_SECRET`; the API then re-checks the internal key,
// so neither side is trusting the other's word alone.
//
// GET, not POST: Vercel cron issues GET requests.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";
// Measuring storage scans every account's graphs and checkpoint blobs, so give it room.
export const maxDuration = 300;

export async function GET(req: Request) {
  const secret = process.env.CRON_SECRET;
  if (secret && req.headers.get("authorization") !== `Bearer ${secret}`) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  const headers = await internalHeaders();
  const results: Record<string, unknown> = {};
  // Reclaim first, then measure — otherwise the figure shown all day is the pre-GC one, which
  // would make the retention window look like it isn't working.
  for (const job of ["checkpoints", "measure-storage"] as const) {
    const r = await fetch(`${API_URL}/internal/gc/${job}`, { method: "POST", headers });
    results[job] = r.ok ? await r.json() : { error: r.status };
  }
  return Response.json(results);
}
