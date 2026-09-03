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
 *
 * `media` is the tone for a label sitting directly on a photograph. It exists because the
 * other two don't survive there: the muted grey-green text measures ~3.8:1 against the
 * brightest patches of the hero art (under AA for 12px), and the `--border-dark-strong`
 * rule is a solid near-black that simply vanishes on a picture. Spectra's answer to type
 * over imagery is full-strength type, never a scrim, so this tone goes to full strength and
 * swaps the rule for a translucent white one.
 */
export function SectionLabel({
  index,
  children,
  tone = "dark",
  className,
}: {
  index?: string;
  children: ReactNode;
  tone?: "dark" | "light" | "media";
  className?: string;
}) {
  const light = tone === "light";
  const media = tone === "media";
  return (
    <div className={cn("flex items-center gap-3", className)}>
      {index ? (
        <span
          className={cn(
            "rounded-[6px] bg-[var(--eyebrow-bg)] px-[7px] py-[3px] font-mono text-xs font-bold tracking-[0.14em]",
            light ? "text-[var(--accent-on-light)]" : "text-[var(--accent-on-dark)]",
          )}
        >
          {index}
        </span>
      ) : null}
      <span
        aria-hidden
        className={cn(
          "h-px w-9",
          media ? "bg-white/30" : light ? "bg-[var(--mist-300)]" : "bg-[var(--border-dark-strong)]",
        )}
      />
      <span
        className={cn(
          "font-mono text-xs font-medium uppercase tracking-[0.14em]",
          media
            ? "text-[var(--text-on-dark)]"
            : light
              ? "text-[var(--text-muted)]"
              : "text-[var(--text-on-dark-muted)]",
        )}
      >
        {children}
      </span>
    </div>
  );
}
