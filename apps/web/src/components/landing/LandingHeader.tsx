"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { SiteLogo } from "@/components/site/Logo";
import { SITE_CTA, SITE_NAV } from "@/components/site/nav";
import { StatusDot } from "@/components/spectra/StatusDot";
import { cn } from "@/lib/utils";

// The site header: transparent, a centred glass nav pill on desktop, a hamburger sheet on
// mobile, the Calypr logo top-left and the CTA top-right.
//
// **One header for every marketing page now.** It floats over the hero on `/` and sticks to the
// top of the scroll on /pricing, /blog, /checkout and /waitlist (`sticky`). It replaced
// `site/Header`, which offered the same destinations in a different visual language — a flat
// bordered bar with sentence-case links — so a visitor arriving on /pricing from search met
// what looked like a different site's nav. Only the CTA still differs, by design (`cta`).
//
// Spectra's layout rules are explicit that the header is transparent and *never* becomes a
// solid bar on scroll, so there is no scroll listener here by design.
//
// `tone` exists because the hero is now the system's one light surface. The mark is a white
// SVG, so on light it gets inverted back to near-black rather than swapped for a second asset.
//
// Links come from `site/nav`, which is also where the two CTAs live.
const NAV = SITE_NAV;

export function LandingHeader({
  tone = "dark",
  cta = SITE_CTA,
  sticky = false,
}: {
  tone?: "dark" | "light";
  /** The call to action, because it is the one thing the two surfaces do *not* share. The
   *  homepage offers "Join Beta" (the still-invite-only free cohort); every other page offers
   *  "Get Started", straight to sign-in. See `SITE_HEADER_CTA`'s doc comment — that difference
   *  is deliberate, and folding the pages onto one header must not quietly erase it. */
  cta?: { label: string; href: string };
  /** Inner pages scroll past their header and want it to follow; the homepage's floats over a
   *  one-viewport hero and must not. */
  sticky?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const light = tone === "light";
  // The pulsing dot means "the beta cohort is open", so it belongs to that CTA and not to
  // whatever else is passed in. On "Get Started" it would be a live-status indicator for
  // nothing.
  const beta = cta.href === SITE_CTA.href;

  // Glass, not a fill: the capsules sit over the hero surface, and blur is the only way this
  // system is allowed to separate an element from what's behind it.
  //
  // On dark that is now `liquid-glass` (globals.css) rather than the 60%-opaque `--glass-dark`
  // slab. The hero can carry a video loop behind these capsules, and a near-opaque fill stops
  // the footage moving through them — which is the entire reason the effect reads as glass.
  // `liquid-glass` supplies its own border as a gradient pseudo-element, so the capsule must
  // *not* also carry a border utility here: two rings, one inside the other.
  //
  // Light keeps the old recipe. It sits over a bright still, where a strong fill is what makes
  // dark type on it legible, and the white-gradient edge would be invisible anyway.
  const capsule = light
    ? "border border-black/[0.08] bg-white/70 backdrop-blur-[20px] backdrop-saturate-150"
    : "liquid-glass";
  const linkColor = light
    ? "text-[var(--text-muted)] hover:bg-black/[0.05] hover:text-[var(--text-heading)]"
    : "text-[var(--text-on-dark-muted)] hover:bg-white/10 hover:text-[var(--text-on-dark)]";

  return (
    <header className={cn("z-20", sticky ? "sticky top-0" : "relative")}>
      <div className="mx-auto flex h-24 w-full max-w-7xl items-center justify-between px-6">
        <Link href="/" aria-label="Calypr home" className="shrink-0" onClick={() => setOpen(false)}>
          {/* `/logo.svg` ships with white fills. Over the dark band it's used as-is; over the
              light hero the alpha silhouette is knocked back to near-black. */}
          <SiteLogo className={cn("h-6 w-auto", light && "[filter:brightness(0)_saturate(0)]")} />
        </Link>

        {/* centred nav pill (desktop) */}
        <nav
          className={cn(
            "hidden items-center gap-1 rounded-full px-2 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] md:flex",
            capsule,
          )}
        >
          {NAV.map(({ label, href }) => (
            <Link
              key={label}
              href={href}
              className={cn(
                "rounded-full px-4 py-1.5 transition-colors duration-200 ease-[var(--ease-standard)]",
                linkColor,
              )}
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* The CTA (desktop). No separate Sign in link — on the homepage the hero button goes
            straight to /sign-in, and on the inner pages this button does, so a second link to
            the same place would be redundant either way. */}
        <div className="hidden shrink-0 items-center gap-2 md:flex">
          <Link
            href={cta.href}
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-5 py-2 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors duration-200 ease-[var(--ease-standard)]",
              capsule,
              light
                ? "text-[var(--text-heading)] hover:border-[var(--border-accent)]"
                // No `hover:border-*` on dark: `liquid-glass` draws its edge as a pseudo-element
                // and has no border to change. The fill lifts instead, which is the same move
                // the Button primitive's `secondary` variant makes.
                : "text-[var(--text-on-dark)] hover:bg-white/[0.08]",
            )}
          >
            {beta ? <StatusDot pulse /> : null}
            {cta.label}
          </Link>
        </div>

        {/* hamburger (mobile) */}
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className={cn(
            "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors duration-200 md:hidden",
            capsule,
            light ? "text-[var(--text-heading)]" : "text-[var(--text-on-dark)]",
          )}
        >
          {open ? <X className="h-5 w-5" strokeWidth={1.75} /> : <Menu className="h-5 w-5" strokeWidth={1.75} />}
        </button>
      </div>

      {/* Mobile sheet. A denser glass mix than the capsules: this panel carries a list of links
          over whatever the hero is showing behind it, and the 1% fill that flatters a two-word
          pill leaves them fighting the picture. See `.liquid-glass` in globals.css. */}
      {open ? (
        <div
          className={cn(
            "mx-6 rounded-2xl p-2 md:hidden",
            capsule,
            !light && "[--liquid-blur:14px] [--liquid-fill:0.06]",
          )}
        >
          <nav className="flex flex-col">
            {NAV.map(({ label, href }) => (
              <Link
                key={label}
                href={href}
                onClick={() => setOpen(false)}
                className={cn(
                  "rounded-xl px-4 py-3 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors duration-200",
                  linkColor,
                )}
              >
                {label}
              </Link>
            ))}
            <Link
              href={cta.href}
              onClick={() => setOpen(false)}
              className="mt-1 inline-flex items-center gap-2 rounded-xl bg-[image:var(--grad-accent)] px-4 py-3 font-mono text-[11px] uppercase tracking-[0.14em] font-bold text-[var(--ink-950)]"
            >
              {beta ? <StatusDot className="bg-[var(--ink-950)] shadow-none" /> : null}
              {cta.label}
            </Link>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
