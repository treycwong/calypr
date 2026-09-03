import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Spectra's pill CTA. Replaces `landing/HoverButton`.
 *
 * **One green `primary` per screen.** `white` is reserved for a CTA sitting on the dark
 * full-bleed band; `solid` and `outline` use 12px corners rather than the pill.
 *
 * Hover never moves the button — the gradient brightens one step and the glow intensifies.
 * Press is `scale(0.98)` with no colour change; disabled is `opacity 0.4` with no
 * desaturation. Those three rules are the whole interaction language of the brand, so
 * they live on the base class rather than per-variant.
 */
const VARIANTS = {
  primary:
    "bg-[image:var(--grad-accent)] text-[var(--ink-950)] font-semibold border border-transparent shadow-[var(--glow-accent)] " +
    "hover:bg-[image:var(--grad-accent-hover)] hover:shadow-[var(--glow-accent-strong)]",
  secondary:
    "bg-white/[0.07] text-[var(--text-on-dark-muted)] border border-[var(--border-dark)] " +
    "hover:bg-white/[0.12] hover:text-[var(--text-on-dark)]",
  white:
    "bg-white text-[var(--ink-950)] font-medium border border-transparent shadow-[var(--glow-white)] " +
    "hover:shadow-[0_0_64px_rgba(255,255,255,0.42)]",
  outline:
    "!rounded-[12px] bg-transparent text-[var(--text-on-dark)] border border-[var(--border-dark-strong)] " +
    "hover:bg-white/[0.04] hover:border-[var(--border-accent)]",
  ghost:
    "bg-transparent text-[var(--text-on-dark-muted)] border border-transparent hover:text-[var(--text-on-dark)]",
} as const;

const SIZES = {
  sm: "px-[18px] py-[9px] text-[13px]",
  md: "px-6 py-[13px] text-[15px]",
  lg: "px-[30px] py-4 text-base",
} as const;

const BASE =
  "group/cta inline-flex items-center justify-center gap-2.5 whitespace-nowrap rounded-full " +
  "font-medium tracking-[-0.01em] transition-all duration-200 ease-[var(--ease-standard)] " +
  "active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40 " +
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-bright)]";

type Common = {
  children: ReactNode;
  variant?: keyof typeof VARIANTS;
  size?: keyof typeof SIZES;
  className?: string;
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  className,
  ...rest
}: Common & ComponentProps<"button">) {
  return (
    <button className={cn(BASE, SIZES[size], VARIANTS[variant], className)} {...rest}>
      {children}
    </button>
  );
}

/** The same surface as a link — what every marketing CTA on the page actually is. */
export function ButtonLink({
  children,
  variant = "primary",
  size = "md",
  className,
  ...rest
}: Common & ComponentProps<typeof Link>) {
  return (
    <Link className={cn(BASE, SIZES[size], VARIANTS[variant], className)} {...rest}>
      {children}
    </Link>
  );
}
