/**
 * Small monochrome marks for the apps and providers a workspace can connect.
 *
 * These are hand-authored rather than pulled from an icon package: lucide dropped brand glyphs in
 * v1, and adding a whole icon dependency for two logos isn't worth the install. They inherit
 * `currentColor` like every other icon in the sidebar, so they sit in a tile unchanged.
 *
 * Providers without a drawn mark fall back to a letterform in the same box — a deliberate,
 * consistent system rather than a half-remembered logo. Swap any of these for the real SVG when
 * you have it; only this file changes.
 */

function GithubMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden className={className}>
      <path d="M12 .5C5.37.5 0 5.87 0 12.5c0 5.3 3.44 9.8 8.21 11.39.6.11.82-.26.82-.58 0-.29-.01-1.05-.02-2.06-3.34.72-4.04-1.61-4.04-1.61-.55-1.39-1.34-1.76-1.34-1.76-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.5.99.11-.78.42-1.31.76-1.61-2.67-.3-5.47-1.34-5.47-5.94 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.53.11-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6.01 0c2.29-1.55 3.3-1.23 3.3-1.23.65 1.65.24 2.88.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.8 5.63-5.48 5.93.43.37.81 1.1.81 2.22 0 1.61-.01 2.9-.01 3.29 0 .32.21.7.83.58A12.01 12.01 0 0 0 24 12.5C24 5.87 18.63.5 12 .5Z" />
    </svg>
  );
}

function NotionMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden className={className}>
      <rect
        x="2.5"
        y="2.5"
        width="19"
        height="19"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      {/* The Notion wordmark's "N": two uprights joined by a diagonal, drawn as strokes so it
          stays legible at 20px. */}
      <path
        d="M8.5 16.5v-9l7 9v-9"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

const DRAWN: Record<string, (p: { className?: string }) => React.JSX.Element> = {
  github: GithubMark,
  notion: NotionMark,
};

/** One or two characters, for a provider with no drawn mark. */
const LETTERS: Record<string, string> = {
  openai: "AI",
  anthropic: "A\\",
  tavily: "T",
  unsplash: "U",
};

export function BrandMark({ kind, className }: { kind: string; className?: string }) {
  const Drawn = DRAWN[kind];
  if (Drawn) return <Drawn className={className ?? "h-5 w-5"} />;
  return (
    <span
      aria-hidden
      className={`flex items-center justify-center rounded-[5px] border border-current/50 font-mono text-[10px] leading-none ${
        className ?? "h-5 w-5"
      }`}
    >
      {LETTERS[kind] ?? kind.slice(0, 2).toUpperCase()}
    </span>
  );
}
