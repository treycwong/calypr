import type { Metadata } from "next";

import { SiteFooter } from "@/components/site/Footer";
import { SITE_HEADER_CTA } from "@/components/site/nav";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { SECTION_INNER } from "@/components/site/Section";
import { GridLines } from "@/components/spectra/GridLines";
import { SectionHeading } from "@/components/spectra/SectionHeading";
import { SectionLabel } from "@/components/spectra/SectionLabel";
import { cn } from "@/lib/utils";

import { WaitlistForm } from "./WaitlistForm";

export const metadata: Metadata = {
  title: "Build updates — Calypr",
  description:
    "Hear about new Calypr blocks, templates and the UI Builder as they ship. No spam, just the occasional build update.",
};

export default function WaitlistPage() {
  return (
    // A build-updates list since the canvas opened to everyone (2026-11): the UI Builder teaser
    // links here. The path stays `/waitlist` so old links and the `waitlist` table still fit.
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
        <SectionLabel index="01">Build updates</SectionLabel>
        <SectionHeading
          size="display"
          accent="as it ships."
          className="mt-6"
          subtitle="New blocks, new templates, and the UI Builder when it lands. No spam, just the occasional build update. Calypr itself is open now: you can start building today."
        >
          Hear what&rsquo;s new
        </SectionHeading>
        <WaitlistForm />
      </main>

      <SiteFooter />
    </div>
  );
}
