"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

// Shared friendly fallback for the App Router error boundaries (error.tsx / global-error.tsx).
// Keeps a render crash from white-screening: shows a card with a retry + a way out.
export function ErrorFallback({
  title = "Something went wrong",
  description = "This part of the app hit an unexpected error.",
  reset,
}: {
  title?: string;
  description?: string;
  reset?: () => void;
}) {
  return (
    <div
      className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center"
      data-testid="error-boundary"
    >
      <span className="font-mono text-3xl text-muted-foreground">⌁</span>
      <h1 className="text-lg font-medium">{title}</h1>
      <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      <div className="flex items-center gap-2">
        {reset ? (
          <button
            type="button"
            onClick={reset}
            className={buttonVariants({ size: "sm" })}
            data-testid="error-retry"
          >
            Try again
          </button>
        ) : null}
        <Link
          href="/dashboard"
          className={buttonVariants({ variant: "outline", size: "sm" })}
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
