import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Spectra's pill CTA. Replaces `landing/HoverButton`.
 *
 * **One green `primary` per screen.** `secondary` is the glass one — the system's default
 * companion to a primary, and what the "line" outline buttons on the marketing pages became.
 * `white` is reserved for a CTA sitting on the dark full-bleed band; `outline` uses 12px
 * corners rather than the pill and is what to reach for on a light surface, where glass has
 * nothing to work with.
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
  // The glass secondary. `liquid-glass` (globals.css) supplies the fill, the blur and the
  // gradient edge, so this variant adds only colour — and deliberately no `border`, because
  // that edge is a pseudo-element and a border utility would draw a second ring inside it.
  //
  // `--liquid-fill` is nudged up from the 1% the hero capsules use. Over a video the fill
  // barely matters — the footage moving through the blur is what reads as glass — but on the
  // flat ink surfaces inside the page there is nothing behind it to blur, so at 1% the button
  // was a bare hairline. 5% keeps it glassy on the hero and gives it a body everywhere else.
  //
  // Dark surfaces only: the edge is a white gradient and the fill is white, so on Spectra's
  // light surfaces this reads as nothing. Use `outline` there.
  secondary:
    "liquid-glass [--liquid-fill:0.05] text-[var(--text-on-dark)] hover:[--liquid-fill:0.1]",
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
