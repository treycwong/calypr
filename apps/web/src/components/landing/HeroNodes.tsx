"use client";

import type React from "react";
import { useEffect, useRef } from "react";

import { TemplateArt } from "@/components/landing/TemplateArt";
import { FEATURED_TEMPLATES } from "@/components/landing/landing-data";
import { cn } from "@/lib/utils";

/**
 * The four cards floating around the hero copy, drifting with the pointer.
 *
 * **They show real things, not mock-ups.** Two carry actual generated output already in the
 * repo — the image the Capabilities section runs its scan over, and the Video block's poster
 * frame — and two carry `TemplateArt` seeded by a real template id, the same deterministic art
 * the templates carousel further down the page draws for that template. A visitor who scrolls
 * meets both again.
 *
 * The mix is deliberate: four abstract gradients read as wallpaper, while a photograph beside a
 * generated diagram reads as a product with range.
 *
 * **One pointer, two responses, both measured from the hero's centre.** Every card drifts
 * (`depth`, per card, so the plane has parallax) and every card rotates (`MAX_TILT`, shared, so
 * they turn as one surface). Neither is driven by hovering a card: the input is where the
 * pointer sits across the whole section, which means the field responds from the moment the
 * pointer enters the hero rather than only when it happens to cross a 200px box, and the four
 * cards always agree about which way the light is coming from.
 *
 * Positions are percentages of the section, not pixels: the hero is `h-screen`, so a fixed
 * offset that clears the headline on a 900px viewport buries it on a 700px one. `depth` is how
 * far each card travels — the point of the parallax is that they move by *different* amounts,
 * so the plane reads as having depth rather than as one image sliding. They are deliberately
 * small (8–17px): the drift is there to separate the cards in depth, not to be noticed on its
 * own, and the rotation is what the eye actually reads.
 */
const CARDS = [
  {
    at: "left-[6%] top-[17%]",
    depth: 13,
    label: "Market research report",
    meta: "RESEARCH",
    seed: FEATURED_TEMPLATES[0].id,
  },
  {
    at: "right-[7%] top-[14%]",
    depth: 8,
    label: "Image generation",
    meta: "GPT-IMAGE-1",
    // A real generated output, not a mock — the same file the Capabilities section runs its
    // scan animation over.
    img: "/capability-image.jpg",
  },
  {
    at: "left-[8%] bottom-[14%]",
    depth: 17,
    label: "Video generation",
    meta: "SEEDANCE",
    img: "/capability-video-poster.jpg",
  },
  {
    at: "right-[5%] bottom-[11%]",
    depth: 10,
    label: "Notion study quiz",
    meta: "CONNECTED APPS",
    seed: FEATURED_TEMPLATES[1].id,
  },
] as const;

/** Degrees at the far edge of the hero.
 *
 *  **The rotation carries the effect and the travel stays small.** Those two are in tension: a
 *  card that both slides and turns a long way reads as unstable — the eye tracks the position
 *  change and the rotation just makes it look like it is wobbling. Cutting `depth` roughly in
 *  half and pushing the angle up trades one for the other, so the cards hold their place on the
 *  page and the plane still turns clearly under the pointer.
 *
 *  Past ~16° the glass edges and the thumbnails start to look sheared rather than tilted. */
const MAX_TILT = 13;

export function HeroNodes({ className }: { className?: string }) {
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    // A pointer device that can hover, and a visitor who hasn't asked for less motion. Touch
    // gets the cards standing still, which is the honest outcome — there is no pointer to
    // follow, and a scroll-driven substitute would be a different effect wearing its clothes.
    const ok =
      window.matchMedia("(hover: hover) and (pointer: fine)").matches &&
      !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!ok) return;

    // The section, not the window: the hero is one viewport, and past it the cards are gone.
    const section = el.parentElement ?? el;
    let frame = 0;
    let tx = 0;
    let ty = 0;
    let x = 0;
    let y = 0;

    const onMove = (e: PointerEvent) => {
      const r = section.getBoundingClientRect();
      // −1..1 from the section's centre — the one number the whole effect is built on. Both
      // the parallax offset and the tilt read it, so a card's drift and its rotation can never
      // disagree about where the pointer is. Clamped, so a pointer leaving the section sideways
      // can't push the cards further than the edges ever would.
      tx = Math.max(-1, Math.min(1, (e.clientX - r.left - r.width / 2) / (r.width / 2)));
      ty = Math.max(-1, Math.min(1, (e.clientY - r.top - r.height / 2) / (r.height / 2)));
      if (!frame) frame = requestAnimationFrame(tick);
    };

    // Eased in rAF rather than a CSS transition on every pointermove: a transition restarts on
    // each event, so fast movement stutters against its own easing. Lerping toward the target
    // gives one continuous motion that settles on its own.
    const tick = () => {
      x += (tx - x) * 0.08;
      y += (ty - y) * 0.08;
      el.style.setProperty("--px", x.toFixed(4));
      el.style.setProperty("--py", y.toFixed(4));
      frame =
        Math.abs(tx - x) > 0.001 || Math.abs(ty - y) > 0.001
          ? requestAnimationFrame(tick)
          : 0;
    };

    // Settle back to centre when the pointer leaves, rather than freezing mid-drift.
    const onLeave = () => {
      tx = 0;
      ty = 0;
      if (!frame) frame = requestAnimationFrame(tick);
    };

    section.addEventListener("pointermove", onMove);
    section.addEventListener("pointerleave", onLeave);
    return () => {
      section.removeEventListener("pointermove", onMove);
      section.removeEventListener("pointerleave", onLeave);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div
      ref={root}
      aria-hidden
      // Decorative and never in the way: the copy and its buttons sit above this on z-10, and
      // nothing here takes a pointer event — otherwise a card overlapping the CTA would eat
      // the click.
      className={cn(
        "pointer-events-none absolute inset-0 z-[6] hidden [--px:0] [--py:0] lg:block",
        className,
      )}
    >
      {CARDS.map((card) => (
        <article
          key={card.label}
          // `pointer-events-auto` against the container's `none`: the tilt needs the card to
          // receive its own pointer events, but the *gaps between* the cards must stay
          // transparent to clicks so nothing can shadow the CTA in the middle.
          className={cn("absolute w-[196px] xl:w-[216px]", card.at)}
          style={{
            transform: `translate3d(calc(var(--px) * ${card.depth}px), calc(var(--py) * ${card.depth}px), 0)`,
          }}
        >
          {/* The system's glass, one step denser than a button: this is a panel with a picture
              and a row of type in it.

              **Two transforms on two elements, deliberately.** The parallax translate lives on
              the `article` and the rotation lives here — one `transform` property cannot hold
              both, and splitting them lets each read the shared pointer values in its own
              units. Nesting composes them.

              No handlers and no transition. Both properties are pure functions of `--px`/`--py`,
              which the rAF loop already eases toward the pointer, so the rotation inherits that
              smoothing for free — a CSS transition on top would only add lag. It also means the
              cards need no pointer events at all: nothing here can shadow a button, and the
              hit-testing bugs that a hover-driven version kept producing are gone by
              construction.

              The `perspective()` is a *function inside this element's own transform*, not the
              `perspective` property on a parent. Both render the same, but this way the whole
              effect is one declaration on one element, with nothing to keep in sync. */}
          <div
            className="liquid-glass overflow-hidden rounded-[18px] p-2 [--liquid-blur:12px] [--liquid-fill:0.05] [transform:perspective(760px)_rotateY(calc(var(--px)*var(--tilt)))_rotateX(calc(var(--py)*var(--tilt)*-1))]"
            style={{ "--tilt": `${MAX_TILT}deg` } as React.CSSProperties}
          >
            <div className="aspect-[16/10] w-full overflow-hidden rounded-[12px]">
              {"img" in card ? (
                // Plain `img`: these are fixed ~200px thumbnails of assets already in `public/`,
                // so `next/image`'s srcset machinery would add a wrapper and a set of variants
                // for a size that never changes.
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={card.img}
                  alt=""
                  loading="lazy"
                  decoding="async"
                  className="h-full w-full object-cover"
                />
              ) : (
                <TemplateArt seed={card.seed} />
              )}
            </div>
            {/* Meta above, title below — the reference's order, and the only one that works:
                side by side, a two-word tag squeezed "Notion study quiz" into "Notion study
                q…". On its own line the title has the full card width. */}
            <div className="px-1 pb-0.5 pt-2">
              <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-[var(--accent-on-dark)]">
                {card.meta}
              </span>
              <p className="mt-1 text-[12.5px] font-medium leading-snug text-[var(--text-on-dark)]">
                {card.label}
              </p>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
