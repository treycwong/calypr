import { Reveal } from "@/components/landing/motion";
import { SECTION_INNER } from "@/components/site/Section";
import { ButtonLink } from "@/components/spectra/Button";
import { SectionHeading } from "@/components/spectra/SectionHeading";

/**
 * The closing invitation. Copy discipline matters here: the page-level E2E uses strict-mode
 * locators, so this section must not repeat "Get Started" (the hero's link).
 */
export function LandingCta() {
  return (
    <section className={`${SECTION_INNER} py-20`}>
      <div className="dotted relative overflow-hidden rounded-[24px] border border-[var(--border-dark)] bg-[var(--surface-card-dark)] px-8 py-24 text-center shadow-[var(--inner-hairline)]">
        {/* The radial green glow behind a closing CTA — one of the system's four background
            devices, and the only place a coloured light is allowed to sit behind type. */}
        <div
          aria-hidden
          className="glow-breathe pointer-events-none absolute inset-x-0 top-0 h-64 bg-[radial-gradient(ellipse_at_center_top,rgba(62,206,139,0.16),transparent_65%)]"
        />
        <Reveal>
          <p className="font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--accent-on-dark)]">
            the canvas is open
          </p>
          <SectionHeading className="mt-5" align="center" size="display" accent="Now">
            Build
          </SectionHeading>
          <p className="mx-auto mt-5 max-w-md text-pretty text-lg leading-[1.55] text-[var(--text-on-dark-muted)]">
            From a prompt to an agent you own. Draw it, run it, take the code with you.
          </p>
          <div className="mt-9 flex items-center justify-center">
            {/* "Try for Free", not "Get Started" — the hero owns that label and the landing
                E2E matches it with a strict-mode locator. */}
            <ButtonLink href="/sign-in" variant="white" size="lg">
              Try for Free
            </ButtonLink>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
