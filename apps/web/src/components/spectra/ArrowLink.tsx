import { ArrowRight } from "lucide-react";
import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Mono uppercase text link with a trailing arrow — the site's tertiary action.
 *
 * The 3px arrow nudge on hover is the *only* translation anywhere in Spectra. Everything
 * else that reacts to a pointer does so by changing colour, border or glow. Don't add a
 * second moving thing here.
 */
const TONES = {
  accent: "text-[var(--accent-on-dark)]",
  accentLight: "text-[var(--accent-on-light)]",
  light: "text-white",
  dark: "text-[var(--text-heading)]",
} as const;

export function ArrowLink({
  children,
  tone = "accent",
  underline = false,
  className,
  ...rest
}: {
  children: ReactNode;
  tone?: keyof typeof TONES;
  underline?: boolean;
  className?: string;
} & ComponentProps<typeof Link>) {
  return (
    <Link
      className={cn(
        "group/arrow inline-flex items-center gap-2 border-b pb-[3px] font-mono text-[11px] font-bold uppercase tracking-[0.14em]",
        "transition-opacity duration-200 ease-[var(--ease-standard)] hover:opacity-75",
        underline ? "border-current" : "border-transparent",
        TONES[tone],
        className,
      )}
      {...rest}
    >
      {children}
      <ArrowRight
        className="h-3.5 w-3.5 transition-transform duration-200 ease-[var(--ease-standard)] group-hover/arrow:translate-x-[3px]"
        strokeWidth={1.75}
      />
    </Link>
  );
}
