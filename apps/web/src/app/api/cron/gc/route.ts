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
  // Fails **closed**, including when the secret is unset. This route holds the internal key and
  // spends it on a delete plus a full-table scan, so an unconfigured deployment must not leave
  // that publicly triggerable — "no secret configured" has to mean "off", not "open". Vercel
  // attaches `Authorization: Bearer $CRON_SECRET` to cron invocations once the var is set.
  const secret = process.env.CRON_SECRET;
  if (!secret) {
    return Response.json({ error: "cron is not configured" }, { status: 503 });
  }
  if (req.headers.get("authorization") !== `Bearer ${secret}`) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }

  const headers = await internalHeaders();
  const results: Record<string, unknown> = {};
  // Reclaim first, then measure — otherwise the figure shown all day is the pre-GC one, which
  // would make the retention window look like it isn't working.
  //
  // Purge before both: it deletes whole accounts, so running it first keeps `measure-storage`
  // from spending a full scan on accounts that are about to stop existing. No new `vercel.json`
  // cron for it — Hobby allows two and one is already spent on this route.
  for (const job of ["purge-accounts", "checkpoints", "measure-storage"] as const) {
    const r = await fetch(`${API_URL}/internal/gc/${job}`, { method: "POST", headers });
    results[job] = r.ok ? await r.json() : { error: r.status };
  }
  return Response.json(results);
}
