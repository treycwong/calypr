export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`flex items-center gap-2 ${className}`}>
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden className="text-foreground">
        <line x1="5" y1="5" x2="5" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
        <line x1="5" y1="5" x2="15" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
        <circle cx="5" cy="5" r="2.4" fill="currentColor" />
        <circle cx="5" cy="15" r="2.4" fill="currentColor" opacity="0.55" />
        <circle cx="15" cy="15" r="2.4" fill="currentColor" opacity="0.8" />
      </svg>
      <span className="font-mono text-sm font-medium tracking-tight">calypr</span>
    </span>
  );
}
