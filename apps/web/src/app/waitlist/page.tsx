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
  title: "Join the Beta team — Calypr",
  description:
    "Join the Calypr beta: get access to the latest product features as we ship them, and help shape the product with your feedback.",
};

export default function WaitlistPage() {
  return (
    // The homepage nav's CTA lands here, so it is the first page after the hero for anyone who
    // takes it — the one inner page where a colour seam would be most visible.
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
        <SectionLabel index="01">Early access</SectionLabel>
        <SectionHeading
          size="display"
          accent="Beta team."
          className="mt-6"
          subtitle="Get access to the latest product features as we ship them, and help shape Calypr with your feedback. No spam — just the occasional build update."
        >
          Join the
        </SectionHeading>
        <WaitlistForm />
      </main>

      <SiteFooter />
    </div>
  );
}
