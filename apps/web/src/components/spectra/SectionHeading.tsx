import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Section titles are always two-tone: a neutral phrase followed by a green one
 * ("Optical **Precision**", "Trusted by **Visionaries**"). Never colour the whole
 * heading — a headline that has no natural break point doesn't fit this system and
 * should be rewritten rather than set flat.
 *
 * Weight stays light (300) at every size and tracking stays negative: the size does the
 * work. Passing `font-semibold` here is always a mistake, which is why the weight isn't
 * a prop.
 */
const SIZES = {
  display: "text-[clamp(2.5rem,6vw,3.5rem)]",
  h1: "text-[clamp(2rem,4.5vw,2.75rem)]",
  h2: "text-[clamp(1.75rem,3.5vw,2.25rem)]",
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
          "font-heading font-light leading-[1.12] tracking-[-0.02em]",
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
