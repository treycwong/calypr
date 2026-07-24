import { Check } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter } from "@/components/site/Footer";
import { SiteHeader } from "@/components/site/Header";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Pricing — Calypr",
  description:
    "Start free with monthly credits — no key, no card. Plus adds code export, more projects, and 2,000 credits a month for $20.",
};

/** The plan matrix from PRICING-SPEC §1, ordered the way a reader evaluates it.
 *
 * Two plans on purpose: a third column invites the "which one am I?" hesitation that costs a
 * signup, and the spec only decides these two. */
const PLANS = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    cadence: "/month",
    pitch: "Build and run real agents. No key, no card.",
    cta: "Start building",
    href: "/canvas",
    featured: false,
    features: [
      "3 projects",
      "100 credits a month, across runs and the assistant",
      "Every block, template and canvas run",
      "Keep going on your own key when the credits run out",
      "Share links, run-capped per link",
    ],
  },
  {
    id: "plus",
    name: "Plus",
    price: "$20",
    cadence: "/month",
    pitch: "Take the code with you, and 20× the monthly credits.",
    cta: "Select plan",
    href: "/checkout?plan=plus",
    featured: true,
    features: [
      "Everything in Free",
      "Code export — edit the generated Python and apply it back to the canvas",
      "20 projects",
      "2,000 credits a month, shared across runs and the assistant",
      "Platform keys on every model — nothing to set up",
      "Your own keys still run free, at zero credits",
      "Credits reset at the start of each month",
    ],
  },
] as const;

export default function PricingPage() {
  return (
    <div className="relative flex min-h-screen flex-col">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_-10%,rgba(255,255,255,0.06),transparent)]"
      />
      <SiteHeader />

      <main className="mx-auto w-full max-w-4xl flex-1 px-5 py-16">
        <div className="text-center">
          <span className="inline-flex items-center rounded-full border border-border bg-card/40 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            pricing
          </span>
          <h1 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
            Plans and pricing
          </h1>
          <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
            Start free with monthly credits — no key, no card, no trial clock. Bring your own key
            when they run out, or upgrade when you want the generated Python in your hands.
          </p>
        </div>

        <div className="mt-12 grid gap-5 sm:grid-cols-2">
          {PLANS.map((plan) => (
            <div
              key={plan.id}
              data-testid={`plan-${plan.id}`}
              className={cn(
                "flex flex-col rounded-xl border bg-card/40 p-6",
                plan.featured ? "border-foreground/30 bg-card/70" : "border-border",
              )}
            >
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold">{plan.name}</h2>
                {plan.featured ? (
                  <span
                    className="rounded-full bg-foreground px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-background"
                    data-testid="plan-recommended"
                  >
                    Recommended
                  </span>
                ) : null}
              </div>

              <div className="mt-4 flex items-baseline gap-1">
                <span className="text-3xl font-semibold tracking-tight">{plan.price}</span>
                <span className="text-sm text-muted-foreground">{plan.cadence}</span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{plan.pitch}</p>

              <ul className="mt-6 flex-1 space-y-3 border-t border-border pt-6">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex gap-2.5 text-sm leading-relaxed">
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              <Link
                href={plan.href}
                data-testid={`plan-${plan.id}-cta`}
                className={cn(
                  buttonVariants({ variant: plan.featured ? "default" : "outline" }),
                  "mt-8 w-full",
                )}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>

        <p className="mt-8 text-center text-xs text-muted-foreground">
          Credits meter what our keys spend on your behalf. Runs on your own key never touch
          them.
        </p>
      </main>

      <SiteFooter />
    </div>
  );
}
