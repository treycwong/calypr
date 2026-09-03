import { cn } from "@/lib/utils";

/**
 * The repeating 1px vertical rule field that underlies full-width sections — one of the
 * four background devices the system permits, and the only one that repeats. Sits behind
 * content, so the parent needs `relative` and `isolate`.
 *
 * The gradient itself is `.grid-lines` in `globals.css`; this is just the positioned box.
 */
export function GridLines({ tone = "dark", className }: { tone?: "dark" | "light"; className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "grid-lines pointer-events-none absolute inset-0 -z-10",
        tone === "light" && "grid-lines-light",
        className,
      )}
    />
  );
}
