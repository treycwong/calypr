import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter } from "@/components/site/Footer";
import { SiteHeader } from "@/components/site/Header";
import { buttonVariants } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Tutorials — Calypr",
  description: "Step-by-step guides for building agents on the Calypr canvas.",
};

export default function TutorialsPage() {
  return (
    <div className="relative flex min-h-full flex-col">
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(60%_50%_at_50%_-10%,rgba(255,255,255,0.06),transparent)]"
      />
      <SiteHeader />

      <main className="mx-auto w-full max-w-4xl flex-1 px-5 py-16">
        <span className="inline-flex items-center rounded-full border border-border bg-card/40 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          tutorials
        </span>
        <h1 className="mt-5 text-3xl font-semibold tracking-tight sm:text-4xl">
          Tutorials are on the way.
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Hands-on guides for the canvas are in progress. In the meantime, the blog has build
          walk-throughs, or you can jump straight into the playground.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/blog" className={buttonVariants({ variant: "outline" })}>
            Read the blog
          </Link>
          <Link href="/canvas" className={buttonVariants()}>
            Open the canvas
          </Link>
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
