import { cn } from "@/lib/utils";

/**
 * A glowing 6px status dot. `pulse` is a slow opacity fade — per the system's motion
 * rules the single continuous animation permitted anywhere in the brand, so resist
 * reaching for it a second time. The keyframes and the reduced-motion opt-out live in
 * `globals.css` as `.spectra-pulse`.
 */
export function StatusDot({ pulse = false, className }: { pulse?: boolean; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--accent-bright)] shadow-[0_0_10px_var(--accent-bright)]",
        pulse && "spectra-pulse",
        className,
      )}
    />
  );
}
