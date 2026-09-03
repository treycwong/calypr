import Image from "next/image";

import { Capabilities } from "@/components/landing/Capabilities";
import { LandingCta } from "@/components/landing/LandingCta";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { ModelsConnectors } from "@/components/landing/ModelsConnectors";
import { TemplatesShowcase } from "@/components/landing/TemplatesShowcase";
import { UiBuilderTeaser } from "@/components/landing/UiBuilderTeaser";
import { SiteFooter } from "@/components/site/Footer";
import { ButtonLink } from "@/components/spectra/Button";
import { SectionLabel } from "@/components/spectra/SectionLabel";

/**
 * The marketing home page, on the Spectra design system.
 *
 * `data-brand="spectra"` is what switches the shadcn semantic tokens over to Spectra's
 * ink/mist surfaces (see the block of that name in `globals.css`). It's scoped to this
 * subtree on purpose: the canvas and dashboard keep their current neutral look until
 * they're redesigned too, at which point the attribute moves up to `<html>` in the root
 * layout and this one comes off.
 */
export default function Home() {
  return (
    <div data-brand="spectra" className="relative flex min-h-screen flex-col bg-background">
      {/*
        A full-viewport, bottom-anchored hero: the art is full-bleed, the nav floats over it
        as a glass pill, and the whole content block is pushed to the bottom edge with
        `mt-auto`. Type sits directly on the picture — no scrim, no gradient overlay, which
        is Spectra's rule for photography as much as it is the reference layout's.

        `h-screen` + `overflow-hidden` makes this exactly one viewport. Everything below is a
        separate scroll; nothing here may grow the section, so the copy block is deliberately
        short and the headline clamps rather than wraps unboundedly.
      */}
      <section className="relative h-screen w-full overflow-hidden">
        {/* The LCP element, so eager + priority. Same asset as always — only its framing has
            changed. It's a plain `inset-0` layer with the readable content stacked over it in
            a `z-10` column, rather than the image pushed to a negative z-index under an
            `isolate` parent. Both paint the same; this way there is no stacking-context
            subtlety to reason about, and nothing later added to the section can accidentally
            slip behind the picture. */}
        <Image
          src="/hero.png"
          alt=""
          aria-hidden
          fill
          priority
          sizes="100vw"
          className="pointer-events-none absolute inset-0 object-cover"
        />

        {/* Everything readable sits in one column over the picture. */}
        <div className="relative z-10 flex h-full w-full flex-col">
          <LandingHeader />

          {/* `mt-auto` is what pins the block to the bottom of the viewport; the container is
              the same `max-w-7xl px-6` the nav, every section below and the footer use, so
              the logo, the headline and every section edge resolve to one left margin. */}
          <div className="mt-auto w-full">
            <div className="mx-auto w-full max-w-7xl px-6 pb-10 sm:pb-14 lg:pb-16">
              <div className="max-w-2xl">
                {/* "Agent builder" is the site's own description of itself (see the root
                    layout's metadata), not new marketing language. */}
                <SectionLabel index="01" tone="media">
                  Agent builder
                </SectionLabel>

                {/*
                  Two-tone display headline: a neutral phrase then a green one. The accessible
                  name has to stay exactly "Build your dreams" — `e2e/tests/landing.spec.ts`
                  matches the heading by that name — so the split is spans inside the one `h1`,
                  never two headings.

                  Weight 300 with -0.03em tracking is the system's display register; the size
                  does the work. On a full-bleed dark photograph the neutral phrase is white and
                  the accent steps up to `--accent-text-quiet` (green-300), which is the ramp
                  Spectra reserves for green type on dark.
                */}
                <h1 className="mt-6 font-heading text-[clamp(2.5rem,6.5vw,5rem)] font-light uppercase leading-[0.92] tracking-[-0.03em]">
                  {/* The `{" "}` is load-bearing, not formatting. Two adjacent block spans
                      concatenate into the accessible name with no separator ("Build
                      yourdreams"), which silently breaks the
                      `getByRole("heading", { name: "Build your dreams" })` locator in
                      `e2e/tests/landing.spec.ts`. It's invisible on screen because each span
                      is `block`. */}
                  <span className="block text-[var(--text-on-dark)]">Build your</span>{" "}
                  <span className="block pl-[0.12em] text-[var(--accent-text-quiet)]">dreams</span>
                </h1>

                {/* Full strength, not the muted token: over the photograph the muted
                    grey-green falls to ~3.8:1 on the brightest patches, under AA at this
                    size. Hierarchy here comes from the size gap to the headline, which is
                    how this system is meant to carry it anyway. */}
                <p className="mt-6 max-w-[480px] text-pretty text-lg leading-[1.55] text-[var(--text-on-dark)]">
                  Create your own AI apps easily.
                </p>

                <div className="mt-8">
                  {/* Billing is live (Plus is self-serve from /pricing), so the hero sends
                      people straight to sign-in rather than the waitlist. "Join Beta" in the
                      nav is the separate, still-invite-only path onto the free beta cohort. */}
                  <ButtonLink href="/sign-in" variant="primary" size="lg">
                    Get Started
                  </ButtonLink>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* inner sections — see components/landing/. Capabilities keeps the #features anchor,
          TemplatesShowcase keeps #templates. */}
      <Capabilities />
      <TemplatesShowcase />
      <ModelsConnectors />
      <UiBuilderTeaser />
      <LandingCta />

      <SiteFooter />
    </div>
  );
}
