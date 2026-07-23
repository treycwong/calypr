import { ArrowUpRight } from "lucide-react";
import Link from "next/link";

import { SiteLogo } from "@/components/site/Logo";

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

function FooterColumn({ title, links }: { title: string; links: FooterLink[] }) {
  return (
    <div>
      <h3 className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
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
    <footer className="mt-auto border-t border-border">
      <div className="mx-auto w-full max-w-6xl px-5 py-14">
        <div className="flex flex-col gap-12 md:flex-row md:justify-between">
          <div className="space-y-3">
            <SiteLogo className="h-5 w-auto" />
            <p className="max-w-[22ch] text-sm text-muted-foreground">
              Design AI Agents on Canvas.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-10 sm:grid-cols-4 md:gap-16">
            {COLUMNS.map((col) => (
              <FooterColumn key={col.title} {...col} />
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
