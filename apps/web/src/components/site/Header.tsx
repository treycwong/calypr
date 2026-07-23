import Link from "next/link";

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
export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/70 backdrop-blur">
      <div className="flex h-14 w-full items-center justify-between gap-4 px-6">
        <Link href="/" aria-label="Calypr home" className="shrink-0">
          <SiteLogo className="h-5 w-auto" />
        </Link>
        <nav className="hidden items-center gap-7 text-xs text-muted-foreground md:flex">
          {SITE_NAV.map(({ label, href }) => (
            <Link key={label} href={href} className="transition-colors hover:text-foreground">
              {label}
            </Link>
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-2">
          <Link href={SITE_HEADER_CTA.href} className={buttonVariants({ size: "sm" })}>
            {SITE_HEADER_CTA.label}
          </Link>
        </div>
      </div>
    </header>
  );
}
