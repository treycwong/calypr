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
export default async function CheckoutPage() {
  const session = await getSession();
  return (
    <div className="relative flex min-h-full flex-col">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_-10%,rgba(255,255,255,0.06),transparent)]"
      />
      <SiteHeader />
      <main className="mx-auto w-full max-w-2xl flex-1 px-5 py-16">
        <CheckoutView email={session?.email ?? ""} />
      </main>
      <SiteFooter />
    </div>
  );
}
