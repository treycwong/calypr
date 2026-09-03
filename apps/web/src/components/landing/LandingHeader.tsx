"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { SiteLogo } from "@/components/site/Logo";
import { SITE_CTA, SITE_NAV } from "@/components/site/nav";
import { StatusDot } from "@/components/spectra/StatusDot";
import { cn } from "@/lib/utils";

// Landing-only header: transparent, floating over the hero. A centred nav pill on desktop, a
// hamburger sheet on mobile, the Calypr logo top-left, and the CTA top-right. Other routes keep
// the standard SiteHeader.
//
// Spectra's layout rules are explicit that the header is transparent and *never* becomes a
// solid bar on scroll, so there is no scroll listener here by design.
//
// `tone` exists because the hero is now the system's one light surface. The mark is a white
// SVG, so on light it gets inverted back to near-black rather than swapped for a second asset.
//
// Links and CTA come from `site/nav`, shared with SiteHeader: the two headers should look
// different and say the same thing. They previously each held their own list and drifted apart.
const NAV = SITE_NAV;

export function LandingHeader({ tone = "dark" }: { tone?: "dark" | "light" }) {
  const [open, setOpen] = useState(false);
  const light = tone === "light";

  // Glass, not a fill: the capsules sit over the hero surface, and blur is the only way this
  // system is allowed to separate an element from what's behind it.
  const capsule = light
    ? "border-black/[0.08] bg-white/70 backdrop-blur-[20px] backdrop-saturate-150"
    : "border-white/10 bg-[var(--glass-dark)] backdrop-blur-[20px] backdrop-saturate-150";
  const linkColor = light
    ? "text-[var(--text-muted)] hover:bg-black/[0.05] hover:text-[var(--text-heading)]"
    : "text-[var(--text-on-dark-muted)] hover:bg-white/10 hover:text-[var(--text-on-dark)]";

  return (
    <header className="relative z-20">
      <div className="mx-auto flex h-24 w-full max-w-7xl items-center justify-between px-6">
        <Link href="/" aria-label="Calypr home" className="shrink-0" onClick={() => setOpen(false)}>
          {/* `/logo.svg` ships with white fills. Over the dark band it's used as-is; over the
              light hero the alpha silhouette is knocked back to near-black. */}
          <SiteLogo className={cn("h-6 w-auto", light && "[filter:brightness(0)_saturate(0)]")} />
        </Link>

        {/* centred nav pill (desktop) */}
        <nav
          className={cn(
            "hidden items-center gap-1 rounded-full border px-2 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] md:flex",
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

        {/* "Join Beta" CTA (desktop). No separate Sign in link — the hero CTA goes straight to
            /sign-in, so this is the one entry point the header needs. */}
        <div className="hidden shrink-0 items-center gap-2 md:flex">
          <Link
            href={SITE_CTA.href}
            className={cn(
              "inline-flex items-center gap-2 rounded-full border px-5 py-2 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors duration-200 ease-[var(--ease-standard)]",
              capsule,
              light
                ? "text-[var(--text-heading)] hover:border-[var(--border-accent)]"
                : "text-[var(--text-on-dark)] hover:border-[var(--border-accent)]",
            )}
          >
            <StatusDot pulse />
            {SITE_CTA.label}
          </Link>
        </div>

        {/* hamburger (mobile) */}
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className={cn(
            "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border transition-colors duration-200 md:hidden",
            capsule,
            light ? "text-[var(--text-heading)]" : "text-[var(--text-on-dark)]",
          )}
        >
          {open ? <X className="h-5 w-5" strokeWidth={1.75} /> : <Menu className="h-5 w-5" strokeWidth={1.75} />}
        </button>
      </div>

      {/* mobile sheet */}
      {open ? (
        <div className={cn("mx-6 rounded-2xl border p-2 md:hidden", capsule)}>
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
              href={SITE_CTA.href}
              onClick={() => setOpen(false)}
              className="mt-1 inline-flex items-center gap-2 rounded-xl bg-[image:var(--grad-accent)] px-4 py-3 font-mono text-[11px] uppercase tracking-[0.14em] font-bold text-[var(--ink-950)]"
            >
              <StatusDot className="bg-[var(--ink-950)] shadow-none" />
              {SITE_CTA.label}
            </Link>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
