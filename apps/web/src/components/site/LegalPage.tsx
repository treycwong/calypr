import type { ReactNode } from "react";

import { LandingHeader } from "@/components/landing/LandingHeader";
import { SiteFooter } from "@/components/site/Footer";
import { SECTION_INNER } from "@/components/site/Section";
import { SITE_HEADER_CTA } from "@/components/site/nav";
import { SectionLabel } from "@/components/spectra/SectionLabel";
import { LEGAL } from "@/lib/legal";
import { cn } from "@/lib/utils";

export type LegalSection = { id: string; title: string; body: ReactNode };

/**
 * The shared frame for /terms and /privacy: the marketing header and footer, a numbered list of
 * sections with a contents list, and body type set for reading rather than scanning. Long-form
 * prose is the one place this site uses a narrow measure (~70ch); a legal page at the section
 * container's full width is a wall nobody reads.
 */
export function LegalPage({
  label,
  title,
  intro,
  sections,
}: {
  label: string;
  title: string;
  intro: ReactNode;
  sections: LegalSection[];
}) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <LandingHeader cta={SITE_HEADER_CTA} sticky />

      <main className={cn(SECTION_INNER, "flex-1 py-20")}>
        <article className="mx-auto max-w-[70ch]">
          <SectionLabel index="01">{label}</SectionLabel>
          <h1 className="mt-6 font-heading text-4xl font-light tracking-[-0.02em] text-[var(--text-on-dark)] sm:text-5xl">
            {title}
          </h1>
          <p className="mt-4 text-sm text-[var(--text-on-dark-faint)]">
            Last updated {LEGAL.lastUpdated}
          </p>
          <div className="mt-8 text-[15px] leading-[1.7] text-[var(--text-on-dark-muted)]">
            {intro}
          </div>

          <nav aria-label="Contents" className="mt-10 rounded-xl border border-white/[0.08] p-5">
            <ol className="grid gap-1.5 text-sm sm:grid-cols-2">
              {sections.map((s, i) => (
                <li key={s.id}>
                  <a
                    href={`#${s.id}`}
                    className="text-[var(--text-on-dark-muted)] transition-colors hover:text-[var(--text-on-dark)]"
                  >
                    {i + 1}. {s.title}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          {sections.map((s, i) => (
            <section key={s.id} id={s.id} className="mt-12 scroll-mt-24">
              <h2 className="font-heading text-xl font-medium tracking-[-0.01em] text-[var(--text-on-dark)]">
                {i + 1}. {s.title}
              </h2>
              <div className="mt-4 space-y-4 text-[15px] leading-[1.7] text-[var(--text-on-dark-muted)] [&_a]:text-[var(--text-on-dark)] [&_a]:underline [&_a]:underline-offset-4 [&_li]:pl-1 [&_strong]:font-medium [&_strong]:text-[var(--text-on-dark)] [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-5">
                {s.body}
              </div>
            </section>
          ))}
        </article>
      </main>

      <SiteFooter />
    </div>
  );
}
