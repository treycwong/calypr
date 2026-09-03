import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The numbered eyebrow that opens every Spectra section: a green mono index in a soft
 * chip, a 36px hairline rule, then the category in wide-tracked uppercase mono.
 *
 * Replaces `site/Eyebrow` on the landing page. The two are not interchangeable — Eyebrow
 * is a bordered pill, this is a rule-and-index row — so the older one stays in place for
 * `/pricing` and `/tutorials` until those move over too.
 *
 * The index is decorative order, not a sequence the reader has to follow; sections run
 * `01`–`04` down the page.
 */
export function SectionLabel({
  index,
  children,
  tone = "dark",
  className,
}: {
  index?: string;
  children: ReactNode;
  tone?: "dark" | "light";
  className?: string;
}) {
  const dark = tone === "dark";
  return (
    <div className={cn("flex items-center gap-3", className)}>
      {index ? (
        <span
          className={cn(
            "rounded-[6px] bg-[var(--eyebrow-bg)] px-[7px] py-[3px] font-mono text-xs font-bold tracking-[0.14em]",
            dark ? "text-[var(--accent-on-dark)]" : "text-[var(--accent-on-light)]",
          )}
        >
          {index}
        </span>
      ) : null}
      <span
        aria-hidden
        className={cn("h-px w-9", dark ? "bg-[var(--border-dark-strong)]" : "bg-[var(--mist-300)]")}
      />
      <span
        className={cn(
          "font-mono text-xs font-medium uppercase tracking-[0.14em]",
          dark ? "text-[var(--text-on-dark-muted)]" : "text-[var(--text-muted)]",
        )}
      >
        {children}
      </span>
    </div>
  );
}
