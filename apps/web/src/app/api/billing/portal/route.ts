// Proxy the "manage subscription" hand-off to the API (server-side), which creates a Stripe
// Customer Portal session and returns its URL for the browser to follow.
//
// Tenant-scoped: the portal session is bound to the signed-in workspace's Stripe customer by
// the API, not by anything the browser sends. The portal (cancel / plan change / payment
// method / invoices) is hosted by Stripe, so no card data reaches us.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const r = await fetch(`${API_URL}/billing/portal`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      // Forwarded so the API can build the return URL back on this origin.
      origin: new URL(req.url).origin,
      ...(await internalHeaders()),
    },
  });
  return new Response(await r.text(), {
    status: r.status,
    headers: { "content-type": "application/json" },
  });
}
