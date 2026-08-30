import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The marketing-page section shell — one source for the page's horizontal rhythm, which every
 * page used to re-type by hand. The `max-w-7xl px-6` container is deliberately the same one
 * `LandingHeader` and the hero headline use: the logo, the hero copy, every section below it
 * and the footer all resolve to a single left edge. Change it here, not per-section.
 *
 * `bleed` drops the horizontal constraint for full-width children (marquees) while keeping the
 * vertical rhythm; those children constrain their own copy with `SECTION_INNER`.
 */
export const SECTION_INNER = "mx-auto w-full max-w-7xl px-6";
export function Section({
  id,
  bleed = false,
  className,
  children,
}: {
  id?: string;
  bleed?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      id={id}
      className={cn(
        bleed ? "w-full py-16" : cn(SECTION_INNER, "py-16"),
        // anchored sections sit under the floating nav when jumped to
        id && "scroll-mt-24",
        className,
      )}
    >
      {children}
    </section>
  );
}
