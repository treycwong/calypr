import Image from "next/image";

import { Capabilities } from "@/components/landing/Capabilities";
import { LandingCta } from "@/components/landing/LandingCta";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { ModelsConnectors } from "@/components/landing/ModelsConnectors";
import { TemplatesShowcase } from "@/components/landing/TemplatesShowcase";
import { UiBuilderTeaser } from "@/components/landing/UiBuilderTeaser";
import { SiteFooter } from "@/components/site/Footer";
import { ButtonLink } from "@/components/spectra/Button";
import { GridLines } from "@/components/spectra/GridLines";
import { MediaFrame } from "@/components/spectra/MediaFrame";
import { Pill } from "@/components/spectra/Pill";
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
        The hero is the system's one *light* full-width surface: a pale mint wash with the
        aurora gradient, an asymmetric two-column opener (label + display headline left,
        media right) and the hero art hard-cropped into a frosted passe-partout.

        This inverts what was here before — a full-bleed dark photo with the copy laid over
        it and two scrims for legibility. Spectra never darkens a photograph with a scrim;
        it crops the image into a frame and puts a blurred capsule on top of it instead, so
        the art keeps its own contrast and the type sits on a surface built for it.
      */}
      <section className="relative isolate overflow-hidden bg-[image:var(--grad-hero-light)] pb-24">
        <GridLines tone="light" />

        <LandingHeader tone="light" />

        <div className="mx-auto grid w-full max-w-7xl grid-cols-1 items-start gap-12 px-6 pb-8 pt-6 lg:grid-cols-2 lg:gap-10 lg:pt-10">
          <div>
            {/* "Agent builder" is the site's own description of itself (see the root
                layout's metadata), not new marketing language. */}
            <SectionLabel index="01" tone="light">
              Agent builder
            </SectionLabel>

            {/*
              Two-tone display headline: a neutral phrase then a green one. The accessible
              name has to stay exactly "Build your dreams" — `e2e/tests/landing.spec.ts`
              matches the heading by that name — so the split is spans inside the one `h1`,
              never two headings.

              Weight 300 with -0.03em tracking is the system's display register. It looks
              wrong at `font-semibold`, which is what every heading on this page used to be.
            */}
            <h1 className="mt-7 font-heading text-[clamp(3rem,8vw,6.5rem)] font-light uppercase leading-[0.92] tracking-[-0.03em]">
              {/* The `{" "}` is load-bearing, not formatting. Two adjacent block spans
                  concatenate into the accessible name with no separator ("Build yourdreams"),
                  which silently breaks the `getByRole("heading", { name: "Build your dreams" })`
                  locator in `e2e/tests/landing.spec.ts`. The space is invisible on screen
                  because each span is `block`. */}
              <span className="block text-[var(--text-heading)]">Build your</span>{" "}
              <span className="block pl-[0.12em] text-[var(--accent-on-light)]">dreams</span>
            </h1>

            <p className="mt-10 max-w-[480px] text-pretty text-lg leading-[1.55] text-[var(--text-body)]">
              Create your own AI apps easily.
            </p>

            <div className="mt-9">
              {/* Billing is live (Plus is self-serve from /pricing), so the hero sends people
                  straight to sign-in rather than the waitlist. "Join Beta" in the nav is the
                  separate, still-invite-only path onto the free beta cohort. */}
              <ButtonLink href="/sign-in" variant="primary" size="lg">
                Get Started
              </ButtonLink>
            </div>
          </div>

          <div className="lg:pt-6">
            <MediaFrame
              frame
              ratio="16 / 11"
              overlay={
                <Pill tone="glass" className="absolute bottom-3.5 right-3.5">
                  Canvas live
                </Pill>
              }
            >
              {/* The LCP element, so eager + priority. Same asset as before — the frame
                  changed, the picture didn't. */}
              <Image
                src="/hero.png"
                alt=""
                aria-hidden
                fill
                priority
                sizes="(min-width: 1024px) 50vw, 100vw"
                className="object-cover"
              />
            </MediaFrame>
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
