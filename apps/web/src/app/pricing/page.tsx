import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter } from "@/components/site/Footer";
import { SiteHeader } from "@/components/site/Header";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Pricing — Calypr",
  description: "Simple, usage-based pricing for the Calypr agent builder.",
};

export default function PricingPage() {
  return (
    <div className="relative flex min-h-full flex-col">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_-10%,rgba(255,255,255,0.06),transparent)]"
      />
      <SiteHeader />

      <main className="mx-auto w-full max-w-4xl flex-1 px-5 py-16">
        <span className="inline-flex items-center rounded-full border border-border bg-card/40 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          pricing
        </span>
        <h1 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
          Pricing, coming soon.
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
          We&rsquo;re finalising simple, usage-based plans. Join the waitlist and we&rsquo;ll
          share pricing before launch — the canvas is free to try today, no card required.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/waitlist" className={buttonVariants()}>
            Join the waitlist
          </Link>
          <Link href="/canvas" className={buttonVariants({ variant: "outline" })}>
            Try the canvas
          </Link>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
