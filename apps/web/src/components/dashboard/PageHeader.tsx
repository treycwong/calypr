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
    <header className={cn("flex items-start justify-between gap-4", className)}>
      <div className="min-w-0">
        <h1 className="font-heading text-2xl font-medium tracking-[-0.02em]">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </header>
  );
}
