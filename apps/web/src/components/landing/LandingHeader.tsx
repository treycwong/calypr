"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { SITE_CTA, SITE_NAV } from "@/components/site/nav";

// Landing-only header: transparent, floating over the hero image. A centred nav pill on
// desktop, a hamburger sheet on mobile, the Calypr logo top-left, and the CTA top-right. Other
// routes keep the standard SiteHeader — this variant assumes a dark, full-bleed backdrop so
// everything is tuned for white-on-media legibility.
//
// Links and CTA come from `site/nav`, shared with SiteHeader: the two headers should look
// different and say the same thing. They previously each held their own list and drifted apart.
const NAV = SITE_NAV;

export function LandingHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="absolute inset-x-0 top-0 z-20">
      <div className="mx-auto flex h-24 w-full max-w-7xl items-center justify-between px-6">
        {/* logo top-left (SVG is dark; invert to white over the media) */}
        <Link href="/" aria-label="Calypr home" className="shrink-0" onClick={() => setOpen(false)}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo.svg"
            alt="Calypr"
            width={87}
            height={25}
            className="h-6 w-auto [filter:brightness(0)_invert(1)]"
          />
        </Link>

        {/* centred nav pill (desktop) */}
        <nav className="hidden items-center gap-1 rounded-full border border-white/10 bg-black/40 px-2 py-1.5 text-sm text-white/70 backdrop-blur-md md:flex">
          {NAV.map(({ label, href }) => (
            <Link
              key={label}
              href={href}
              className="rounded-full px-4 py-1.5 transition-colors hover:bg-white/10 hover:text-white"
            >
              {label}
            </Link>
          ))}
        </nav>

        {/* sign in + waitlist CTA (desktop). The hero CTA points at the waitlist because the
            beta is invite-only, so this is the way back in for people who already have an
            account — us, and the partners we've let in. */}
        <div className="hidden shrink-0 items-center gap-2 md:flex">
          <Link
            href="/sign-in"
            className="rounded-full px-4 py-2 text-sm text-white/70 transition-colors hover:text-white"
          >
            Sign in
          </Link>
          <Link
            href={SITE_CTA.href}
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/40 px-5 py-2 text-sm font-medium text-white backdrop-blur-md transition-colors hover:bg-black/60"
          >
            <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px] shadow-emerald-400/60" />
            {SITE_CTA.label}
          </Link>
        </div>

        {/* hamburger (mobile) */}
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-white/10 bg-black/40 text-white backdrop-blur-md transition-colors hover:bg-black/60 md:hidden"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* mobile sheet */}
      {open ? (
        <div className="mx-4 rounded-2xl border border-white/10 bg-black/70 p-2 backdrop-blur-md md:hidden">
          <nav className="flex flex-col">
            {NAV.map(({ label, href }) => (
              <Link
                key={label}
                href={href}
                onClick={() => setOpen(false)}
                className="rounded-xl px-4 py-3 text-sm text-white/80 transition-colors hover:bg-white/10 hover:text-white"
              >
                {label}
              </Link>
            ))}
            <Link
              href="/sign-in"
              onClick={() => setOpen(false)}
              className="rounded-xl px-4 py-3 text-sm text-white/80 transition-colors hover:bg-white/10 hover:text-white"
            >
              Sign in
            </Link>
            <Link
              href={SITE_CTA.href}
              onClick={() => setOpen(false)}
              className="mt-1 inline-flex items-center gap-2 rounded-xl bg-white px-4 py-3 text-sm font-medium text-black transition-colors hover:bg-white/90"
            >
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              {SITE_CTA.label}
            </Link>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
