import type { Metadata } from "next";

import { CheckoutView } from "@/components/checkout/checkout-view";
import { SiteFooter } from "@/components/site/Footer";
import { SiteHeader } from "@/components/site/Header";
import { getSession } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Checkout — Calypr",
  description: "Upgrade to Calypr Plus.",
  // Nothing here should be indexed: it's a transactional step, not a landing page.
  robots: { index: false, follow: false },
};

/**
 * The checkout step. Today it summarises the plan and takes an email; Week 9 replaces the
 * primary action with a Stripe Checkout Session (`POST /api/billing/checkout` → redirect).
 *
 * Deliberately a real page rather than a disabled button on /pricing: it is the seam Stripe
 * slots into, and standing it up now means the intent it captures — who tried to pay before
 * we could take money — is the list we open billing with.
 */
/** Ask the API whether checkout can take a payment. Server-side so the page renders the truth
 * on first paint rather than making someone click "pay" to find out. Any failure reads as "not
 * yet" — the fallback captures intent, which is the safe direction to be wrong in. */
async function billingEnabled(): Promise<boolean> {
  const api = process.env.CALYPR_API_URL ?? "http://localhost:8000";
  try {
    const r = await fetch(`${api}/billing/status`, { cache: "no-store" });
    return r.ok && Boolean((await r.json()).enabled);
  } catch {
    return false;
  }
}

export default async function CheckoutPage() {
  const [session, enabled] = await Promise.all([getSession(), billingEnabled()]);
  return (
    <div className="relative flex min-h-screen flex-col">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_-10%,rgba(255,255,255,0.06),transparent)]"
      />
      <SiteHeader />
      <main className="mx-auto w-full max-w-2xl flex-1 px-5 py-16">
        <CheckoutView email={session?.email ?? ""} enabled={enabled} />
      </main>
      <SiteFooter />
    </div>
  );
}
