import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Section titles are always two-tone: a neutral phrase followed by a green one
 * ("Optical **Precision**", "Trusted by **Visionaries**"). Never colour the whole
 * heading — a headline that has no natural break point doesn't fit this system and
 * should be rewritten rather than set flat.
 *
 * Tracking stays negative and the size does most of the work. Weight is **per register, not
 * per instance**: the `display` size — the hero-scale headline that opens a page or closes it
 * — is 400, and the section registers below it stay at the system's light 300. Spectra sets
 * every heading at 300; at 5rem over a photograph and on the closing CTA band that read as
 * thin rather than as quiet, so the largest register was stepped up one notch. It is one step,
 * once: `font-semibold` is still always a mistake here, which is why the weight isn't a prop.
 */
const SIZES = {
  display: "text-[clamp(2.5rem,6vw,3.5rem)] font-normal",
  h1: "text-[clamp(2rem,4.5vw,2.75rem)] font-light",
  h2: "text-[clamp(1.75rem,3.5vw,2.25rem)] font-light",
} as const;

export function SectionHeading({
  children,
  accent,
  subtitle,
  tone = "dark",
  align = "left",
  size = "h1",
  id,
  className,
}: {
  children: ReactNode;
  accent?: ReactNode;
  subtitle?: ReactNode;
  tone?: "dark" | "light";
  align?: "left" | "center";
  size?: keyof typeof SIZES;
  id?: string;
  className?: string;
}) {
  const dark = tone === "dark";
  return (
    <div className={cn(align === "center" && "text-center", className)}>
      <h2
        id={id}
        className={cn(
          // Weight rides with the size — see `SIZES`.
          "font-heading leading-[1.12] tracking-[-0.02em]",
          SIZES[size],
          dark ? "text-[var(--text-on-dark)]" : "text-[var(--text-heading)]",
        )}
      >
        {children}
        {accent ? (
          <>
            {" "}
            <span className={dark ? "text-[var(--accent-on-dark)]" : "text-[var(--accent-on-light)]"}>
              {accent}
            </span>
          </>
        ) : null}
      </h2>
      {subtitle ? (
        <p
          className={cn(
            "mt-4 max-w-[62ch] text-pretty leading-[1.55]",
            align === "center" && "mx-auto",
            dark ? "text-[var(--text-on-dark-muted)]" : "text-[var(--text-body)]",
          )}
        >
          {subtitle}
        </p>
      ) : null}
    </div>
  );
}
