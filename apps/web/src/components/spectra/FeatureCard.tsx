import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

import { Card, CardDivider } from "@/components/spectra/Card";
import { IconChip } from "@/components/spectra/IconChip";
import { cn } from "@/lib/utils";

/**
 * The three-up technology card: icon chip, title, body, hairline divider, mono footer with
 * an arrow that is transparent until the card is lit. The generous 44px gap under the chip
 * is from the source, not an accident — it's what gives the card its instrument-panel feel.
 */
export function FeatureCard({
  icon,
  title,
  body,
  meta,
  featured = false,
  className,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  meta?: string;
  featured?: boolean;
  className?: string;
}) {
  return (
    <Card featured={featured} className={cn("group/card p-7", className)}>
      <IconChip tone={featured ? "accent" : "neutral"}>{icon}</IconChip>
      <h3 className="mb-3 mt-11 text-xl font-medium tracking-[-0.02em] text-[var(--text-on-dark)]">
        {title}
      </h3>
      <p className="text-pretty text-[15px] leading-[1.55] text-[var(--text-on-dark-muted)]">{body}</p>
      {meta ? (
        <div className="mt-auto pt-7">
          <CardDivider className="mt-0" />
          <div className="flex items-center justify-between">
            <span
              className={cn(
                "font-mono text-xs font-bold uppercase tracking-[0.14em] transition-colors duration-200",
                featured
                  ? "text-[var(--accent-on-dark)]"
                  : "text-[var(--text-on-dark-faint)] group-hover/card:text-[var(--accent-on-dark)]",
              )}
            >
              {meta}
            </span>
            <ArrowRight
              className={cn(
                "h-4 w-4 text-[var(--accent-on-dark)] transition-opacity duration-200",
                featured ? "opacity-100" : "opacity-0 group-hover/card:opacity-100",
              )}
              strokeWidth={1.75}
            />
          </div>
        </div>
      ) : null}
    </Card>
  );
}
