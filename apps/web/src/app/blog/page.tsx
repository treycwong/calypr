import type { Metadata } from "next";

import { SiteFooter } from "@/components/site/Footer";
import { SITE_HEADER_CTA } from "@/components/site/nav";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { SECTION_INNER } from "@/components/site/Section";
import { GridLines } from "@/components/spectra/GridLines";
import { SectionHeading } from "@/components/spectra/SectionHeading";
import { SectionLabel } from "@/components/spectra/SectionLabel";
import { getPosts } from "@/lib/blog";
import { cn } from "@/lib/utils";

import { PostList } from "./PostList";

export const metadata: Metadata = {
  title: "Blog — Calypr",
  description: "Tutorials and product updates from Calypr — the no-ceiling agent builder.",
};

/** The post index, on the Spectra design system — same eyebrow, heading and container as
 *  /pricing and the landing sections. */
export default async function BlogIndex() {
  const posts = await getPosts();

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
        <SectionLabel index="01">Writing</SectionLabel>
        <SectionHeading
          size="display"
          accent="product updates"
          className="mt-6"
          subtitle="Build guides for the canvas, and what shipped — straight from the repo."
        >
          Tutorials &amp;
        </SectionHeading>

        {/* Capped rather than full-bleed: a list of prose reads at ~75ch, and the 1280px
            container the cards above use would set every description as one long line. */}
        <div className="mt-14 max-w-4xl">
          <PostList posts={posts} />
        </div>
      </main>

      <SiteFooter />
    </div>
  );
}
