import Link from "next/link";

import { AuthField } from "@/components/auth/AuthField";
import { SocialSignIn } from "@/components/auth/social-sign-in";
import { Button } from "@/components/ui/button";

/**
 * The shared shell behind `/sign-in` and `/sign-up`. Both pages post to the same Better Auth
 * endpoints — social sign-in creates the user on first use — so they differ only in wording.
 *
 * This stays a **server component**: the E2E suite clicks the sign-in button the moment the HTML
 * lands (see the note in `e2e/tests/helpers.ts`), so the card must be server-rendered and must
 * never wait on the client. `AuthField` is the one client leaf, painted underneath.
 */

// Better Auth's OAuth callback redirects failures to the `errorCallbackURL` the sign-in button
// sets (`/sign-in`), with a machine-readable `error` code — the codes below are the ones its
// callback route actually emits. We translate only the failures a visitor can act on; everything
// else gets a generic line, and the raw code is never echoed back into the page.
const ERROR_COPY: Record<string, string> = {
  // The link was refused: the existing account's email was never verified by its provider, so it
  // can't be used as proof of ownership. Signing in the original way still works.
  unable_to_link_account:
    "That email is already registered with a different sign-in method. Continue with the provider you signed up with.",
  account_already_linked_to_different_user:
    "That account is already linked to a different Calypr user.",
  // The visitor pressed "Cancel" on the provider's consent screen.
  access_denied: "Sign-in was cancelled.",
};

function errorMessage(code: string): string {
  return ERROR_COPY[code] ?? "Something went wrong signing you in. Please try again.";
}

function Notice({ children, testId }: { children: React.ReactNode; testId: string }) {
  return (
    <div
      className="mb-4 w-full rounded-lg border border-white/10 bg-white/5 p-4 text-sm text-white/80 backdrop-blur"
      data-testid={testId}
    >
      {children}
    </div>
  );
}

export function AuthPanel({
  title,
  subtitle,
  next,
  enabled,
  error,
  children,
  footer,
}: {
  title: string;
  subtitle: string;
  next?: string;
  /** Whether Better Auth is configured. When false we render the keyless dev sign-in instead. */
  enabled: boolean;
  error?: string;
  /** Extra notices above the card — today only the account-deleted message on `/sign-in`. */
  children?: React.ReactNode;
  footer: React.ReactNode;
}) {
  const devAction = `/api/auth/dev${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  return (
    <main className="relative flex min-h-full flex-1 items-center justify-center overflow-hidden bg-[#04060a] p-6 text-white">
      <AuthField />
      <div className="relative z-10 flex w-full max-w-sm flex-col items-center">
        <Link href="/" className="mb-8 flex items-center gap-2">
          <svg width="22" height="22" viewBox="0 0 20 20" aria-hidden className="text-brand">
            <line x1="5" y1="5" x2="5" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
            <line x1="5" y1="5" x2="15" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
            <circle cx="5" cy="5" r="2.4" fill="currentColor" />
            <circle cx="5" cy="15" r="2.4" fill="currentColor" opacity="0.55" />
            <circle cx="15" cy="15" r="2.4" fill="currentColor" opacity="0.8" />
          </svg>
          <span className="font-sans text-sm font-medium tracking-tight text-white">calypr</span>
        </Link>

        {children}
        {error ? <Notice testId="auth-error-notice">{errorMessage(error)}</Notice> : null}

        <div className="w-full rounded-xl border border-cyan-400/15 bg-white/[0.04] p-6 shadow-[0_0_120px_-30px_rgba(34,211,238,0.45)] backdrop-blur-xl">
          <h1 className="text-lg font-medium tracking-tight text-white">{title}</h1>
          <p className="mt-1 text-sm text-white/60">
            {enabled ? subtitle : "Development sign-in — set Better Auth keys to enable real auth."}
          </p>
          <div className="mt-5">
            {enabled ? (
              <div className="flex flex-col gap-2">
                <SocialSignIn provider="github" next={next} />
                <SocialSignIn provider="google" next={next} variant="outline" />
              </div>
            ) : (
              <form method="post" action={devAction}>
                <Button type="submit" className="w-full" data-testid="dev-sign-in">
                  Continue
                </Button>
              </form>
            )}
          </div>
          <p className="mt-5 text-center text-xs text-white/50">{footer}</p>
        </div>

        <p className="mt-6 font-mono text-[11px] text-white/40">prompt → canvas → code</p>
      </div>
    </main>
  );
}
