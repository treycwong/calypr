/** Shared relative-time formatting for list rows ("3m ago", "2d ago", then a date).
 *
 * Lived in `dashboard/page.tsx` until the Playground's History tab needed the same thing.
 * Extracted rather than copied so the two lists can't drift into describing the same instant
 * differently. */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}
