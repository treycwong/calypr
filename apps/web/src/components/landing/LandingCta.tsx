import { ArrowRight } from "lucide-react";

import { HoverButton } from "@/components/landing/HoverButton";
import { Reveal } from "@/components/landing/motion";
import { SECTION_INNER } from "@/components/site/Section";

/**
 * The closing invitation. Copy discipline matters here: the page-level E2E uses strict-mode
 * locators, so this section must not repeat "Get Started" (the hero's link).
 */
export function LandingCta() {
  return (
    <section className={`${SECTION_INNER} py-20`}>
      <div className="dotted relative overflow-hidden rounded-2xl border border-border bg-card/30 px-8 py-24 text-center">
        {/* breathing cyan glow behind the headline */}
        <div
          aria-hidden
          className="glow-breathe pointer-events-none absolute inset-x-0 top-0 h-64 bg-[radial-gradient(ellipse_at_center_top,rgba(34,211,238,0.14),transparent_65%)]"
        />
        <Reveal>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-brand">
            the canvas is open
          </p>
          <h2 className="mx-auto mt-4 max-w-3xl text-5xl font-semibold tracking-tight sm:text-7xl">
            Build Now
          </h2>
          <p className="mx-auto mt-5 max-w-md text-sm leading-relaxed text-muted-foreground sm:text-base">
            From a prompt to an agent you own. Draw it, run it, take the code with you.
          </p>
          <div className="mt-9 flex items-center justify-center">
            {/* "Try for Free", not "Get Started" — the hero owns that label and the landing
                E2E matches it with a strict-mode locator. */}
            <HoverButton href="/sign-in">
              Try for Free <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover/cta:translate-x-0.5" />
            </HoverButton>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
