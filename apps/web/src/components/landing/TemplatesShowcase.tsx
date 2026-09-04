import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { Carousel, CarouselSlide } from "@/components/landing/Carousel";
import { Marquee } from "@/components/landing/Marquee";
import { TemplateArt } from "@/components/landing/TemplateArt";
import { Reveal } from "@/components/landing/motion";
import {
  CATEGORY_ORDER,
  FEATURED_TEMPLATES,
  FRAMEWORK_NAMES,
} from "@/components/landing/landing-data";
import { ArrowLink } from "@/components/spectra/ArrowLink";
import { SectionHeading } from "@/components/spectra/SectionHeading";
import { SectionLabel } from "@/components/spectra/SectionLabel";
import { Section } from "@/components/site/Section";

/**
 * The template gallery — a scroll-snap carousel through the top six templates (mirrored from
 * the compiler's registry, see landing-data.ts), each slide walking through how the graph
 * works in three beats, with the agent-architecture ladder as a chip row. The E2E-required
 * exact text "Reflexion" renders in that chip row and nowhere else on the page.
 */
export function TemplatesShowcase() {
  return (
    <>
      <Section id="templates">
        <Reveal>
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div className="max-w-3xl">
              <SectionLabel index="03">template gallery</SectionLabel>
              {/* The heading was already two-tone; `SectionHeading` is where that split now
                  lives, so the green phrase can't drift from the rest of the page. */}
              <SectionHeading className="mt-6" size="display" accent="agent.">
                Start with a ready-made
              </SectionHeading>
              <p className="mt-5 max-w-xl text-pretty text-lg leading-[1.55] text-[var(--text-on-dark-muted)]">
                Nineteen use-case templates, ten agent architectures. Load one, run it, keep
                the code.
              </p>
            </div>
            <ArrowLink href="/canvas" tone="accent" className="mb-1 hidden sm:inline-flex">
              browse all
            </ArrowLink>
          </div>
        </Reveal>

        {/* the architecture ladder — chip row */}
        <Reveal delay={0.1} className="mt-8 flex flex-wrap items-center gap-2">
          <span className="mr-1 font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--text-on-dark-faint)]">
            frameworks
          </span>
          {FRAMEWORK_NAMES.map((name) => (
            <span
              key={name}
              className="rounded-full border border-border bg-card/40 px-3 py-1 font-mono text-[11px] text-muted-foreground transition-colors hover:border-[var(--border-accent)] hover:text-foreground"
            >
              {name}
            </span>
          ))}
        </Reveal>

        <Reveal delay={0.15}>
          <Carousel className="mt-10">
            {FEATURED_TEMPLATES.map((tpl, i) => (
              <CarouselSlide key={tpl.id}>
                <article className="group grid h-full overflow-hidden rounded-xl border border-border bg-card/30 sm:grid-cols-[1fr_220px]">
                  <div className="flex flex-col p-7">
                    <div className="flex items-baseline gap-4">
                      <span className="font-mono text-[11px] tracking-[0.2em] text-muted-foreground">
                        {String(i + 1).padStart(2, "0")} / {String(FEATURED_TEMPLATES.length).padStart(2, "0")}
                      </span>
                      <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-brand/80">
                        {tpl.category}
                      </span>
                    </div>
                    <h3 className="mt-4 font-heading text-2xl font-medium tracking-tight sm:text-3xl">
                      {tpl.name}
                    </h3>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{tpl.blurb}</p>
                    <ol className="mt-6 space-y-3 border-t border-border pt-5">
                      {tpl.how.map((beat, j) => (
                        <li key={j} className="flex gap-3 text-sm leading-relaxed text-muted-foreground">
                          <span className="font-mono text-[11px] leading-6 text-brand">
                            {String(j + 1).padStart(2, "0")}
                          </span>
                          {beat}
                        </li>
                      ))}
                    </ol>
                  </div>
                  <div className="relative hidden overflow-hidden border-l border-border sm:block">
                    <div className="h-full w-full transition-transform duration-700 ease-out group-hover:scale-[1.05]">
                      <TemplateArt seed={tpl.id} />
                    </div>
                  </div>
                </article>
              </CarouselSlide>
            ))}
            {/* closing slide → the other thirteen live on the canvas */}
            <CarouselSlide className="max-w-sm">
              <Link
                href="/canvas"
                className="dotted group flex h-full min-h-[280px] flex-col items-start justify-end rounded-xl border border-border bg-card/20 p-7 transition-colors hover:bg-card/40"
              >
                <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                  + 13 more
                </span>
                <span className="mt-2 inline-flex items-center gap-2 font-heading text-2xl font-medium tracking-tight">
                  Browse them all
                  <ArrowRight className="h-5 w-5 text-brand transition-transform duration-300 group-hover:translate-x-0.5" />
                </span>
              </Link>
            </CarouselSlide>
          </Carousel>
        </Reveal>
      </Section>

      {/* category marquee — an editorial breath between the gallery and the stack */}
      <div className="border-y border-border py-6">
        <Marquee duration={55} className="[--marquee-gap:3rem]">
          {CATEGORY_ORDER.map((cat) => (
            <span key={cat} className="flex items-center gap-12 whitespace-nowrap">
              <span className="font-heading text-4xl font-medium tracking-tight text-transparent [-webkit-text-stroke:1px_color-mix(in_oklab,var(--foreground)_35%,transparent)] sm:text-5xl">
                {cat}
              </span>
              <span className="h-1.5 w-1.5 rounded-full bg-brand" />
            </span>
          ))}
        </Marquee>
      </div>
    </>
  );
}
