"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { SiteLogo } from "@/components/site/Logo";
import { SITE_HEADER_CTA, SITE_NAV } from "@/components/site/nav";
import { buttonVariants } from "@/components/ui/button";

// Shared sticky site nav (pricing, blog, checkout, tutorials). The landing page uses
// `LandingHeader` instead — it floats over the hero media and is styled for white-on-image
// legibility — but both take their *links* from `site/nav`, so the two can look different
// without offering different destinations. The CTA is intentionally not shared; see
// `SITE_HEADER_CTA`'s doc comment.
//
// Full-bleed rather than centred on a max-width: the pages below it are narrow, and a nav that
// stops short of the viewport edges reads as a different site from the landing page's.
//
// No separate "Sign in" link: "Get Started" already goes straight to /sign-in, so a second
// link to the same destination in the same header would be redundant — same reasoning as the
// homepage nav.
//
// Mobile: a hamburger opens a dropdown sheet with the nav links + CTA, mirroring
// `LandingHeader`'s pattern (same behaviour, restyled for this header's flat surface rather
// than the glassy-over-photo look). Previously there was no mobile nav at all — the CTA button
// just sat alone at the top right on every viewport, with no way to reach Features/Templates/
// Blog/Tutorials/Pricing from a phone.
export function SiteHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/70 backdrop-blur">
      <div className="flex h-14 w-full items-center justify-between gap-4 px-6">
        <Link
          href="/"
          aria-label="Calypr home"
          className="shrink-0"
          onClick={() => setOpen(false)}
        >
          <SiteLogo className="h-5 w-auto" />
        </Link>
        <nav className="hidden items-center gap-7 text-xs text-muted-foreground md:flex">
          {SITE_NAV.map(({ label, href }) => (
            <Link key={label} href={href} className="transition-colors hover:text-foreground">
              {label}
            </Link>
          ))}
        </nav>
        <div className="hidden shrink-0 items-center gap-2 md:flex">
          <Link href={SITE_HEADER_CTA.href} className={buttonVariants({ size: "sm" })}>
            {SITE_HEADER_CTA.label}
          </Link>
        </div>

        {/* hamburger (mobile only) */}
        <button
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border/60 text-foreground transition-colors hover:bg-muted md:hidden"
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* mobile sheet */}
      {open ? (
        <div className="border-t border-border/60 bg-background px-4 pb-3 pt-1 md:hidden">
          <nav className="flex flex-col">
            {SITE_NAV.map(({ label, href }) => (
              <Link
                key={label}
                href={href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-3 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                {label}
              </Link>
            ))}
            <Link
              href={SITE_HEADER_CTA.href}
              onClick={() => setOpen(false)}
              className={`${buttonVariants({ size: "sm" })} mt-2 w-full`}
            >
              {SITE_HEADER_CTA.label}
            </Link>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
