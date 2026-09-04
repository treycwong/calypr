import type { ReactNode } from "react";

import { StatusDot } from "@/components/spectra/StatusDot";
import { cn } from "@/lib/utils";

/**
 * Rounded status capsule. The `glass` tone is how Spectra labels imagery: the brand never
 * darkens a photograph with a scrim gradient, it puts a blurred capsule on top of it
 * instead. That's the only place transparency and blur are allowed at all.
 */
const TONES = {
  dark: "bg-[var(--ink-850)] text-[var(--text-on-dark)] border-[var(--border-dark)]",
  glass: "bg-[rgba(6,17,12,0.72)] text-white border-white/[0.12] backdrop-blur-[20px] backdrop-saturate-150",
  light: "bg-white text-[var(--text-heading)] border-[var(--border-light)]",
  accent: "bg-[var(--accent-soft-bg)] text-[var(--accent-on-dark)] border-[var(--border-accent)]",
} as const;

export function Pill({
  children,
  dot = true,
  tone = "dark",
  className,
}: {
  children: ReactNode;
  dot?: boolean;
  tone?: keyof typeof TONES;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3.5 py-[7px] font-mono text-[11px] font-bold uppercase tracking-[0.14em]",
        TONES[tone],
        className,
      )}
    >
      {dot ? <StatusDot /> : null}
      {children}
    </span>
  );
}
