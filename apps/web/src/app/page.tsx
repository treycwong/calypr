import { Capabilities } from "@/components/landing/Capabilities";
import { HeroNodes } from "@/components/landing/HeroNodes";
import { LandingCta } from "@/components/landing/LandingCta";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { ModelsConnectors } from "@/components/landing/ModelsConnectors";
import { TemplatesShowcase } from "@/components/landing/TemplatesShowcase";
import { UiBuilderTeaser } from "@/components/landing/UiBuilderTeaser";
import { SiteFooter } from "@/components/site/Footer";
import { ButtonLink } from "@/components/spectra/Button";

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
      <section className="relative h-screen w-full overflow-hidden bg-[var(--ink-950)]">
        {/*
          The ground is flat ink now — no photograph, no loop. With four cards floating around a
          centred column, the cards *are* the picture; anything moving behind them was a second
          subject competing for the same attention, which is why the video kept needing to be
          dimmed further until it was barely there anyway.

          What replaces it is one soft glow at the top, which does the job the footage was
          actually doing: it stops a full-viewport flat black reading as an unpainted page, and
          it puts the brightest part of the frame behind the nav, so the headline below sits in
          the darker half and gains contrast for free.

          Two ellipses rather than one. The wide neutral wash is the light itself, and it is
          off-white rather than green because a green glow at this size tints the whole upper
          third and makes the accent word downstream look washed out — the first pass at this
          did exactly that. The narrower green pass sits inside it at very low alpha and is what
          keeps the light on-brand instead of generic. Both originate slightly *above* the top
          edge, so the brightest point of the falloff is off-screen and what shows is the
          gradient rather than a clipped hotspot. Both are `blur`-free gradients — a blurred element here would cost a
          composited layer the size of the viewport for the same result.
        */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 z-[1] h-[64vh] bg-[radial-gradient(85%_100%_at_50%_-8%,rgba(226,240,233,0.11)_0%,rgba(226,240,233,0.04)_40%,transparent_74%)]"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 z-[1] h-[52vh] bg-[radial-gradient(50%_100%_at_50%_-10%,rgba(62,206,139,0.07)_0%,rgba(62,206,139,0.025)_45%,transparent_78%)]"
        />

        {/* The floating template cards. Above the glow, below the copy. */}
        <HeroNodes />

        {/* Everything readable sits in one column over the ground.

            `pointer-events-none` on the column, `auto` on the header and the copy inside it.
            The cards themselves need no pointer events — the tilt reads the pointer's position
            across the whole section, not a hover — so this is belt-and-braces rather than
            load-bearing. It stays because it costs two classes and it is what keeps a
            full-viewport invisible box from quietly swallowing anything added here later. */}
        <div className="pointer-events-none relative z-10 flex h-full w-full flex-col">
          <div className="pointer-events-auto">
            <LandingHeader />
          </div>

          {/* Centred, vertically and horizontally: the headline is the middle of the frame and
              the cards orbit it. `min-h-0` lets this flex child actually shrink on short
              viewports instead of pushing the block off the bottom edge. */}
          <div className="flex min-h-0 flex-1 items-center justify-center">
            <div className="pointer-events-auto mx-auto w-full max-w-7xl px-6 pb-16 text-center">
              {/*
                Two-tone display headline: a neutral phrase then a green one. The accessible
                name has to stay exactly "Craft your next agentic app" —
                `e2e/tests/landing.spec.ts` matches the heading by that name — so the split is
                spans inside the one `h1`, never two headings.

                Centred, so the two lines are `block` with no left indent: the old
                `pl-[0.12em]` on the second line was optical correction for a flush-left
                setting and reads as a mistake once the lines are centred.

                **Weight 600, sentence case, a step smaller than the rest of the display
                register.** The hero is the one place on the site that sets type this large, and
                at 5.5rem the 400 the `display` register uses read as thin rather than as quiet
                — the reference carries its headline on weight, not on size. Dropping the
                ceiling from 5.5rem to 4.5rem is what buys the weight.

                Leading goes from 0.95 to 1.0 with the case change: 0.95 is a setting for caps,
                which have no descenders. In sentence case the "y" of "your" collides with the
                cap-height of the line under it at that value.
              */}
              <h1 className="mx-auto max-w-4xl font-heading text-[clamp(2.5rem,6vw,4.5rem)] font-semibold leading-[1.0] tracking-[-0.03em]">
                {/* The `{" "}` is load-bearing, not formatting. Two adjacent block spans
                    concatenate into the accessible name with no separator ("Craft your
                    nextagentic app"), which silently breaks the
                    `getByRole("heading", { name: "…" })` locator in
                    `e2e/tests/landing.spec.ts`. It's invisible on screen because each span
                    is `block`.

                    **The gradient is what makes the weight read.** Both lines are painted with
                    `bg-clip-text` rather than a flat colour: brightest at the cap line and
                    falling off toward the baseline, which is how a heavy face catches light and
                    is the trick the reference is using. Flat 600 at this size looked blunt; the
                    same 600 under a top-lit gradient looks set rather than typed.

                    `text-transparent` is doing the reveal, so if `background-clip: text` ever
                    fails the text would vanish — hence `[@supports(not(background-clip:text))]`
                    putting the solid colour back. Every browser this app supports has it; the
                    guard costs one class and removes the failure mode entirely.

                    **`pb-[0.14em]` is the fix for clipped descenders, not spacing.** The
                    background is painted in the element's own box and only *then* clipped to
                    the glyphs, so anything hanging below that box — the tails of "g", "y", "p"
                    — gets no paint and simply disappears. At `leading-[1.0]` the box is exactly
                    one em, which is shorter than the font's descent, so "agentic app" lost the
                    bottom of both descenders. The padding grows the paint box; the matching
                    `-mt` on the second line takes the added height back out of the layout, so
                    the two lines sit exactly where they did. */}
                <span className="block bg-gradient-to-b from-white via-white to-[#b9cdc3] bg-clip-text pb-[0.14em] text-transparent [@supports(not(background-clip:text))]:text-[var(--text-on-dark)]">
                  Craft your next
                </span>{" "}
                <span className="-mt-[0.14em] block bg-gradient-to-b from-[#b4ecce] via-[#86d6a8] to-[#3ece8b] bg-clip-text pb-[0.14em] text-transparent [@supports(not(background-clip:text))]:text-[var(--accent-text-quiet)]">
                  agentic app
                </span>
              </h1>

              {/* Full strength, not the muted token: over the picture the muted grey-green
                  falls to ~3.8:1 on the brightest patches, under AA at this size. Hierarchy
                  here comes from the size gap to the headline, which is how this system is
                  meant to carry it anyway. */}
              <p className="mx-auto mt-6 max-w-[46ch] text-pretty text-lg leading-[1.55] text-[var(--text-on-dark)]">
                Draw an agent on a canvas, run it, and take the Python with you. No ceiling.
              </p>

              {/* `flex-wrap` rather than a fixed row: at 320px the two capsules do not fit
                  side by side, and wrapping is the only outcome that keeps both tappable. */}
              <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
                {/* Billing is live (Plus is self-serve from /pricing), so the hero sends
                    people straight to sign-in rather than the waitlist. "Join Beta" in the
                    nav is the separate, still-invite-only path onto the free beta cohort. */}
                <ButtonLink
                  href="/sign-in"
                  variant="primary"
                  size="md"
                  className="sm:px-[30px] sm:py-4 sm:text-base"
                >
                  Get Started
                </ButtonLink>
                {/* The secondary action is the glass one, and it points at the section
                    immediately below — what someone not ready to sign up wants. */}
                <ButtonLink
                  href="#features"
                  variant="secondary"
                  size="md"
                  className="sm:px-[30px] sm:py-4 sm:text-base"
                >
                  See what it builds
                </ButtonLink>
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
