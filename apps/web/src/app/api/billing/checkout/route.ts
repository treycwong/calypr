// Proxy the checkout hand-off to the API (server-side), which creates the Stripe Checkout
// Session and returns its URL for the browser to follow.
//
// Tenant-scoped: the session is attributed to the signed-in user's workspace, and the API
// stamps that workspace id onto the Stripe session so the completed-payment webhook knows
// whose plan to upgrade. Nothing the browser sends decides that.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  // Which plan to buy, and nothing else from the browser. This proxy used to forward no body at
  // all, so a Starter checkout silently became a Plus one. The API reads the plan back off the
  // price actually paid, so this choice can only ever buy what it charges for.
  const body = (await req.json().catch(() => ({}))) as { plan?: unknown };
  const plan = typeof body.plan === "string" ? body.plan : undefined;
  const r = await fetch(`${API_URL}/billing/checkout`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      // Forwarded so the API can build success/cancel URLs back on this origin.
      origin: new URL(req.url).origin,
      ...(await internalHeaders()),
    },
    body: JSON.stringify(plan ? { plan } : {}),
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
