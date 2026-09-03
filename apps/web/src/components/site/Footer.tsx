import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { SiteLogo } from "@/components/site/Logo";
import { SECTION_INNER } from "@/components/site/Section";

// Shared site footer (marketing pages). v0-style multi-column layout: brand mark on the
// left, link columns on the right. `mt-auto` + the flex-column page layout keep it pinned
// to the bottom of the viewport on short pages. Links marked `external` open in a new tab
// and show an arrow; the rest are placeholders (#) until their destinations exist.
type FooterLink = { label: string; href: string; external?: boolean };

const COLUMNS: { title: string; links: FooterLink[] }[] = [
  {
    title: "Product",
    links: [
      { label: "Home", href: "/" },
      { label: "Templates", href: "/#templates" },
      { label: "Pricing", href: "/pricing" },
      { label: "Canvas", href: "/canvas" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "#" },
      { label: "Terms", href: "#" },
      { label: "Privacy", href: "#" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Docs", href: "#" },
      { label: "Blog", href: "/blog" },
      { label: "FAQs", href: "#" },
      { label: "GitHub", href: "#", external: true },
    ],
  },
  {
    title: "Social",
    links: [
      { label: "Twitter", href: "#", external: true },
      { label: "LinkedIn", href: "#", external: true },
    ],
  },
];

/** Spectra numbers its footer columns in mono, the same way it numbers sections and
 *  pricing tiers. The index is decorative order, not a sequence to follow. */
function FooterColumn({ index, title, links }: { index: string; title: string; links: FooterLink[] }) {
  return (
    <div>
      <h3 className="flex items-baseline gap-2 font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--text-on-dark-muted)]">
        <span className="text-[var(--accent-on-dark)]">{index}</span>
        {title}
      </h3>
      <ul className="mt-4 space-y-3">
        {links.map(({ label, href, external }) => (
          <li key={label}>
            {external ? (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {label}
                <ArrowUpRight className="h-3.5 w-3.5" />
              </a>
            ) : (
              <Link
                href={href}
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {label}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SiteFooter() {
  return (
    <footer className="relative isolate mt-auto overflow-hidden border-t border-border">
      {/*
        The giant ghosted wordmark bleeding off the bottom edge — the last of the system's
        four background devices. It's *set type*, not the logo: `SiteLogo` above is still the
        mark. Rendered aria-hidden at ~3.5% opacity so it reads as a watermark rather than a
        heading, and clipped by the footer's `overflow-hidden`.
      */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 -bottom-[0.28em] select-none text-center font-heading text-[clamp(6rem,22vw,18rem)] font-light leading-none tracking-[0.02em] text-[var(--text-on-dark)] opacity-[0.035]"
      >
        CALYPR
      </span>

      {/* Same container as `Section`/`LandingHeader` so the footer's logo lines up with the
          hero's and with every section edge above it. */}
      <div className={`${SECTION_INNER} relative py-14`}>
        <div className="flex flex-col gap-12 md:flex-row md:justify-between">
          <div className="space-y-3">
            <SiteLogo className="h-5 w-auto" />
            <p className="max-w-[22ch] text-[15px] leading-[1.55] text-[var(--text-on-dark-muted)]">
              Design AI Agents on Canvas.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-10 sm:grid-cols-4 md:gap-16">
            {COLUMNS.map((col, i) => (
              <FooterColumn key={col.title} index={`0${i + 1}`} {...col} />
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
