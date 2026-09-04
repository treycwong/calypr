import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Mono, uppercase, letter-spaced micro-label: plan tiers, MOST POPULAR, version tags. */
const TONES = {
  accent: "bg-[var(--accent-soft-bg)] text-[var(--accent-on-dark)] border-[var(--border-accent)]",
  accentSolid: "bg-[image:var(--grad-accent)] text-[var(--ink-950)] border-transparent",
  neutralDark: "bg-white/[0.06] text-[var(--text-on-dark-faint)] border-[var(--border-dark)]",
  neutralLight: "bg-[var(--surface-chip-light)] text-[var(--text-muted)] border-[var(--border-light)]",
} as const;

export function Badge({
  children,
  tone = "accent",
  className,
  ...rest
}: {
  children: ReactNode;
  tone?: keyof typeof TONES;
  className?: string;
  /** `data-testid`, `id`, `title` — see `Card`. */
} & Omit<ComponentProps<"span">, "className" | "children">) {
  return (
    <span
      {...rest}
      className={cn(
        "inline-flex items-center gap-2 rounded-[6px] border px-2 py-1 font-mono text-[11px] font-bold uppercase tracking-[0.14em]",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
