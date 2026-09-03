import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Spectra's card anatomy, and the one surface recipe the whole system leans on:
 * 24px radius, a **flat** fill, a 1px `rgba(255,255,255,0.07)` hairline border and an
 * inset top highlight — deliberately *not* a drop shadow. Dark surfaces in this brand get
 * their depth from borders and inner light; the only true shadows allowed on dark are the
 * media drop and the two coloured glows.
 *
 * `featured` is the one card per row that swaps the flat fill for a gradient, the border
 * for 40%-opacity green, and adds the accent glow. Use it at most once in a grid — a row
 * where everything is featured has nothing featured.
 *
 * Hover goes green at the border and nothing moves, which is the system-wide rule.
 */
export function Card({
  children,
  featured = false,
  interactive = true,
  className,
}: {
  children: ReactNode;
  featured?: boolean;
  /** Set false for a static panel that shouldn't light up under the pointer. */
  interactive?: boolean;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative flex h-full flex-col rounded-[24px] border shadow-[var(--inner-hairline)]",
        "transition-colors duration-200 ease-[var(--ease-standard)]",
        featured
          ? "border-[var(--border-accent)] bg-[image:var(--grad-card-dark)] shadow-[var(--inner-hairline),var(--glow-accent)]"
          : "border-[var(--border-dark)] bg-[var(--surface-card-dark)]",
        interactive && !featured && "hover:border-[var(--border-accent)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

/**
 * The full-width hairline that separates a card's body from its mono footer row.
 * Spectra spaces it 26px above and 18px below, every time.
 */
export function CardDivider({ className }: { className?: string }) {
  return <div aria-hidden className={cn("mb-[18px] mt-[26px] h-px bg-[var(--border-dark)]", className)} />;
}
