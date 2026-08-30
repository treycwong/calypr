import type { ReactNode } from "react";

/**
 * The mono section label pill. Lived as a private helper in the landing page (and was re-typed
 * by hand on /pricing and /tutorials); shared so every marketing surface says "section" the
 * same way. `accent` adds the pulsing brand dot used for coming-soon / live markers.
 */
export function Eyebrow({ children, accent = false }: { children: ReactNode; accent?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-border bg-card/40 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
      {accent && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-60 motion-reduce:animate-none" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand" />
        </span>
      )}
      {children}
    </span>
  );
}
