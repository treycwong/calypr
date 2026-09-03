import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The 48px rounded-square icon container that opens a feature card. Icons are otherwise
 * bare in this system — a chip is the one place a glyph carries its own background.
 *
 * Pass a Lucide element at 22px, `strokeWidth={1.75}` (the brand's stroke).
 */
const TONES = {
  neutral: "bg-white/[0.05] text-[var(--text-on-dark)] border-[var(--border-dark)]",
  accent: "bg-[var(--accent-soft-bg)] text-[var(--accent-bright)] border-[var(--border-accent)]",
  light: "bg-[var(--surface-chip-light)] text-[var(--text-heading)] border-[var(--border-light)]",
} as const;

export function IconChip({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: keyof typeof TONES;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-[12px] border transition-all duration-200 ease-[var(--ease-standard)]",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
