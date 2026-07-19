import type { Metadata } from "next";

import { SiteFooter } from "@/components/site/Footer";
import { SiteHeader } from "@/components/site/Header";

import { WaitlistForm } from "./WaitlistForm";

export const metadata: Metadata = {
  title: "Join the waitlist — Calypr",
  description: "Get early access to Calypr — design AI agents on a canvas, leave with the code.",
};

export default function WaitlistPage() {
  return (
    <div className="relative flex min-h-full flex-col">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_-10%,rgba(255,255,255,0.06),transparent)]"
      />
      <SiteHeader />

      <main className="mx-auto w-full max-w-4xl flex-1 px-5 py-16">
        <span className="inline-flex items-center rounded-full border border-border bg-card/40 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          early access
        </span>
        <h1 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
          Join the waitlist.
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Be first to know when new nodes, templates, and hosted runs land. No spam — just the
          occasional build update.
        </p>
        <WaitlistForm />
      </main>

      <SiteFooter />
    </div>
  );
}
