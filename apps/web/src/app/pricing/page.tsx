import { Check } from "lucide-react";
import type { Metadata } from "next";

import { SiteFooter } from "@/components/site/Footer";
import { SITE_HEADER_CTA } from "@/components/site/nav";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { SECTION_INNER } from "@/components/site/Section";
import { Badge } from "@/components/spectra/Badge";
import { ButtonLink } from "@/components/spectra/Button";
import { Card, CardDivider } from "@/components/spectra/Card";
import { GridLines } from "@/components/spectra/GridLines";
import { SectionHeading } from "@/components/spectra/SectionHeading";
import { SectionLabel } from "@/components/spectra/SectionLabel";
import { FREE_FEATURES, PLUS_FEATURES } from "@/lib/plans";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Pricing — Calypr",
  description:
    "Start free with monthly credits — no key, no card. Plus adds code export, three workspaces, 20 projects, and 2,000 credits a month for $20.",
};

/** The plan matrix from PRICING-SPEC §1, ordered the way a reader evaluates it.
 *
 * Two plans on purpose: a third column invites the "which one am I?" hesitation that costs a
 * signup, and the spec only decides these two. */
const PLANS = [
  {
    id: "free",
    name: "Free",
    index: "01",
    price: "$0",
    cadence: "/month",
    pitch: "Build and run real agents. No key, no card.",
    cta: "Start building",
    href: "/canvas",
    featured: false,
    features: FREE_FEATURES,
  },
  {
    id: "plus",
    name: "Plus",
    index: "02",
    price: "$20",
    cadence: "/month",
    pitch: "Take the code with you, room to organise it, and 20× the monthly credits.",
    cta: "Select plan",
    href: "/checkout?plan=plus",
    featured: true,
    features: PLUS_FEATURES,
  },
] as const;

/**
 * Plans and pricing, on the Spectra design system.
 *
 * `data-brand="spectra"` is the same switch the landing page uses (see the block of that name
 * in `globals.css`): it repoints the shadcn semantic tokens — and `--brand` — at Spectra's
 * ink/green surfaces for this subtree. Without it the page rendered on the neutral shadcn dark
 * palette while the shared footer below it was already using Spectra's tokens, so a visitor
 * arriving from the homepage crossed a colour seam mid-scroll.
 *
 * The container, the numbered eyebrow, the two-tone heading and the card anatomy are the
 * landing page's, not new ones — /pricing is the page a visitor lands on straight from search,
 * and it has to read as the same product.
 */
export default function PricingPage() {
  return (
    <div
      data-brand="spectra"
      className="flex min-h-screen flex-col bg-background"
    >
      <LandingHeader cta={SITE_HEADER_CTA} sticky />

      <main className={cn("relative isolate", SECTION_INNER, "flex-1 py-20")}>
        {/* The rule field belongs to the *content*, not the page. Mounted on the wrapper it
            ran the full document height and struck vertical lines straight through the footer,
            which reads as the background showing through a panel that is meant to be solid.
            Scoped here it stops exactly where the content does. */}
        <GridLines />
        <div className="flex flex-col items-center text-center">
          <SectionLabel index="01">Pricing</SectionLabel>
          <SectionHeading
            size="display"
            align="center"
            accent="pricing"
            className="mt-6"
            subtitle="Start free with monthly credits — no key, no card, no trial clock. Bring your own key when they run out, or upgrade when you want the generated Python in your hands."
          >
            Plans and
          </SectionHeading>
        </div>

        {/* Capped narrower than the section container: two cards stretched to 1280px turn a
            comparison into two unrelated columns. */}
        <div className="mx-auto mt-16 grid max-w-4xl gap-6 sm:grid-cols-2">
          {PLANS.map((plan) => (
            <Card key={plan.id} featured={plan.featured} className="p-8" data-testid={`plan-${plan.id}`}>
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-baseline gap-2.5">
                  <span className="font-mono text-xs font-bold tracking-[0.14em] text-[var(--accent-on-dark)]">
                    {plan.index}
                  </span>
                  <h2 className="text-xl font-medium tracking-[-0.02em] text-[var(--text-on-dark)]">
                    {plan.name}
                  </h2>
                </div>
                {plan.featured ? (
                  <Badge tone="accentSolid" data-testid="plan-recommended">
                    Recommended
                  </Badge>
                ) : null}
              </div>

              {/* The price is display type, not a bolded body number: weight stays light and the
                  size does the work, which is the system's rule for every large figure. */}
              <div className="mt-7 flex items-baseline gap-1.5">
                <span className="font-heading text-[3.25rem] font-light leading-none tracking-[-0.03em] text-[var(--text-on-dark)]">
                  {plan.price}
                </span>
                <span className="text-sm text-[var(--text-on-dark-muted)]">{plan.cadence}</span>
              </div>
              <p className="mt-3 text-pretty text-[15px] leading-[1.55] text-[var(--text-on-dark-muted)]">
                {plan.pitch}
              </p>

              <CardDivider />

              <ul className="flex-1 space-y-3.5">
                {plan.features.map((feature) => (
                  <li
                    key={feature}
                    className="flex gap-3 text-[15px] leading-[1.5] text-[var(--text-on-dark-muted)]"
                  >
                    <Check
                      className="mt-[3px] h-4 w-4 shrink-0 text-[var(--accent-on-dark)]"
                      strokeWidth={2}
                    />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              <ButtonLink
                href={plan.href}
                variant={plan.featured ? "primary" : "secondary"}
                className="mt-9 w-full"
                data-testid={`plan-${plan.id}-cta`}
              >
                {plan.cta}
              </ButtonLink>
            </Card>
          ))}
        </div>

        <p className="mx-auto mt-10 max-w-xl text-center text-sm leading-[1.55] text-[var(--text-on-dark-faint)]">
          Credits meter what our keys spend on your behalf. Runs on your own key never touch
          them.
        </p>
      </main>

      <SiteFooter />
    </div>
  );
}
