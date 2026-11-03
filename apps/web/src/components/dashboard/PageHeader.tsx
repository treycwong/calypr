import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * The one heading pattern for every page under /dashboard: title, optional muted subtitle,
 * optional right-aligned actions. Pages differ in width and content, never in how they open —
 * that sameness is most of what makes an app feel like one product rather than a set of screens.
 *
 * Product register, not marketing: Figtree 500 at 24px. The website's display headings are set
 * light (300) at far larger sizes; at 24px in a dense UI that weight reads as faint.
 */
export function PageHeader({
  title,
  subtitle,
  actions,
  className,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    // Stacks on a phone: side by side, a search box and a button left the title a few letters
    // wide and drawn underneath them.
    <header
      className={cn(
        "flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4",
        className,
      )}
    >
      <div className="min-w-0">
        <h1 className="font-heading text-2xl font-medium tracking-[-0.02em]">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2 sm:shrink-0">{actions}</div> : null}
    </header>
  );
}
