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
import { CREDIT_GUIDE, PLAN_LIMITS, PLANS as PLAN_DATA } from "@/lib/plans";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Pricing — Calypr",
  description:
    "Start free with monthly credits, no key and no card. Starter is 500 credits a month for $5; Plus adds code export, three workspaces and 1,000 credits a month for $10.",
};

/** The three plans of the 2026-10-14 retier (TODO.md §3a), cheapest first, which is the order a
 *  reader compares them in. Names, prices and features come from `@/lib/plans`, the module
 *  checkout and Settings also read, so the card and the receipt can't disagree. */
const PLANS = [
  { ...PLAN_DATA.free, index: "01", cta: "Start building", href: "/canvas", featured: false },
  {
    ...PLAN_DATA.starter,
    index: "02",
    cta: "Choose Starter",
    href: "/checkout?plan=starter",
    // The founder's call (2026-10-15): Starter is the plan to sell, the daily-practice tier.
    featured: true,
  },
  {
    ...PLAN_DATA.plus,
    index: "03",
    cta: "Choose Plus",
    href: "/checkout?plan=plus",
    featured: false,
  },
];

/**
 * Plans and pricing, on the Spectra design system.
 *
 * The container, the numbered eyebrow, the two-tone heading and the card anatomy are the
 * landing page's, not new ones — /pricing is the page a visitor lands on straight from search,
 * and it has to read as the same product.
 */
export default function PricingPage() {
  return (
    <div
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
            subtitle="Every plan runs every block, Video and 3D included. Start free with monthly credits, no key and no card. Pay for more credits when you use them daily, or for Plus when you want the generated Python in your hands."
          >
            Plans and
          </SectionHeading>
        </div>

        {/* Capped narrower than the section container: cards stretched to 1280px turn a
            comparison into unrelated columns. One column until there is room for all three
            side by side; two-then-one at tablet width would orphan Plus on its own row. */}
        <div className="mx-auto mt-16 grid max-w-6xl gap-6 lg:grid-cols-3">
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
                  ${plan.price}
                </span>
                <span className="text-sm text-[var(--text-on-dark-muted)]">/month</span>
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

        {/* "500 credits" means nothing until it is a number of things. Measured from production
            usage, so it moves when the providers' prices do. */}
        <section
          className="mx-auto mt-16 max-w-2xl"
          aria-labelledby="credit-guide"
          data-testid="credit-guide"
        >
          <h2
            id="credit-guide"
            className="text-center font-mono text-xs font-bold uppercase tracking-[0.14em] text-[var(--accent-on-dark)]"
          >
            What a credit buys
          </h2>
          <Card className="mt-5 p-0">
            <table className="w-full text-left text-[15px]">
              <thead>
                <tr className="text-[var(--text-on-dark-faint)]">
                  <th className="px-6 pb-2 pt-5 text-xs font-medium">One run of</th>
                  <th className="px-6 pb-2 pt-5 text-right text-xs font-medium">Credits</th>
                </tr>
              </thead>
              <tbody>
                {CREDIT_GUIDE.map((row) => (
                  <tr key={row.what} className="border-t border-white/[0.06]">
                    <td className="px-6 py-3 text-[var(--text-on-dark-muted)]">{row.what}</td>
                    <td className="px-6 py-3 text-right font-mono text-sm tabular-nums text-[var(--text-on-dark)]">
                      {row.credits}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
          <p className="mt-5 text-center text-sm leading-[1.55] text-[var(--text-on-dark-faint)]">
            So {PLAN_LIMITS.starter.credits} credits is about nine videos, or thousands of text
            runs. Credits reset each month and only meter what our keys spend for you; runs on
            your own key never touch them.
          </p>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
