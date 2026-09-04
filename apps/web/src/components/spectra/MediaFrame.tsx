import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The rounded photographic frame. Everything visual in Spectra is hard-cropped into a
 * 16px-radius rectangle — nothing is feathered, masked, or given a coloured overlay.
 *
 * `frame` adds the frosted white passe-partout used once, on the hero. `overlay` is where
 * glass `Pill`s go; they're absolutely positioned against the inner box.
 *
 * Takes children rather than a `src` so it works over `next/image`, `<video>` and the
 * hand-built SVG visuals alike — the bundle's version only handled `<img>`.
 */
export function MediaFrame({
  children,
  overlay,
  ratio = "16 / 10",
  frame = false,
  className,
}: {
  children: ReactNode;
  overlay?: ReactNode;
  ratio?: string;
  frame?: boolean;
  className?: string;
}) {
  const inner = (
    <div
      className="relative isolate overflow-hidden rounded-[16px] bg-[var(--ink-800)] [&>img]:h-full [&>img]:w-full [&>img]:object-cover"
      style={{ aspectRatio: ratio }}
    >
      {children}
      {overlay}
    </div>
  );

  if (!frame) {
    return <div className={cn("rounded-[16px] shadow-[var(--shadow-media)]", className)}>{inner}</div>;
  }
  return (
    <div
      className={cn(
        "rounded-[32px] border border-white/60 bg-[var(--glass-light)] p-4 shadow-[var(--shadow-panel-light)] backdrop-blur-[20px] backdrop-saturate-150",
        className,
      )}
    >
      {inner}
    </div>
  );
}
