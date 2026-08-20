"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { authClient } from "@/lib/auth-client";

export type SocialProvider = "github" | "google";

function GithubMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
      <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
    </svg>
  );
}

// Google's mark is trademarked and must keep its four brand colours — unlike GithubMark it
// deliberately does not inherit `currentColor`.
function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden>
      <path
        fill="#4285F4"
        d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
      />
      <path
        fill="#34A853"
        d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
      />
      <path
        fill="#FBBC05"
        d="M3.97 10.72a5.41 5.41 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
      />
      <path
        fill="#EA4335"
        d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
      />
    </svg>
  );
}

const PROVIDERS: Record<SocialProvider, { label: string; mark: () => React.ReactElement }> = {
  github: { label: "Continue with GitHub", mark: GithubMark },
  google: { label: "Continue with Google", mark: GoogleMark },
};

/**
 * One social sign-in button. Sign-in and sign-up post to the same Better Auth endpoint — it
 * creates the user on first use — so the two pages differ only in their heading, never here.
 */
export function SocialSignIn({
  provider,
  next,
  variant = "default",
}: {
  provider: SocialProvider;
  next?: string;
  variant?: "default" | "outline";
}) {
  const [busy, setBusy] = useState(false);
  const { label, mark: Mark } = PROVIDERS[provider];
  return (
    <Button
      className="w-full"
      variant={variant}
      disabled={busy}
      data-testid={`${provider}-sign-in`}
      onClick={async () => {
        setBusy(true);
        await authClient.signIn.social({
          provider,
          callbackURL: next ?? "/dashboard",
          // Without this, a failed callback lands on Better Auth's own `/api/auth/error` page —
          // a bare error string on a blank document. Send failures back to the page they started
          // from, which knows how to say what went wrong.
          errorCallbackURL: "/sign-in",
        });
      }}
    >
      <Mark /> {label}
    </Button>
  );
}
