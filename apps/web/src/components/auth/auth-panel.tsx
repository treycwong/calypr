import Link from "next/link";

import { AuthField } from "@/components/auth/AuthField";
import { SocialSignIn } from "@/components/auth/social-sign-in";
import { SiteLogo } from "@/components/site/Logo";
import { Button, buttonVariants } from "@/components/ui/button";

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

/**
 * The auth pages' own header: the wordmark, and the one link the other page needs.
 *
 * Not `SiteHeader` — that carries the full marketing nav and a "Get Started" CTA pointing at
 * `/sign-in`, which from `/sign-in` is a link to itself. Someone here is mid-sign-in; the only
 * navigation worth offering is the other half of the pair.
 */
function AuthNav({ action }: { action: { label: string; href: string } }) {
  return (
    <header className="absolute inset-x-0 top-0 z-20 border-b border-white/10">
      <div className="flex h-16 w-full items-center justify-between gap-4 px-6">
        <Link href="/" aria-label="Calypr home" className="shrink-0">
          <SiteLogo className="h-5 w-auto" />
        </Link>
        <Link
          href={action.href}
          className={buttonVariants({ variant: "outline", size: "sm" })}
          data-testid="auth-nav-action"
        >
          {action.label}
        </Link>
      </div>
    </header>
  );
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
  navAction,
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
  /** The other auth page, for the top-right nav button. */
  navAction: { label: string; href: string };
}) {
  const devAction = `/api/auth/dev${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  return (
    <main className="relative flex min-h-full flex-1 items-center justify-center overflow-hidden bg-[#04060a] p-6 text-white">
      <AuthField />
      <AuthNav action={navAction} />
      <div className="relative z-10 flex w-full max-w-sm flex-col items-center">
        {children}
        {error ? <Notice testId="auth-error-notice">{errorMessage(error)}</Notice> : null}

        <div className="w-full rounded-xl border border-cyan-400/15 bg-white/[0.04] p-6 shadow-[0_0_120px_-30px_rgba(34,211,238,0.45)] backdrop-blur-xl">
          <h1 className="text-lg font-medium tracking-tight text-white">{title}</h1>
          <p className="mt-1 text-sm text-white/60">
            {enabled ? subtitle : "Development sign-in — set Better Auth keys to enable real auth."}
          </p>
          <div className="mt-5">
            {enabled ? (
              // One visual weight for every provider. Making one of them the filled button
              // recommends it, and we have no basis for that — either is a first-class way in.
              <div className="flex flex-col gap-2">
                <SocialSignIn provider="github" next={next} />
                <SocialSignIn provider="google" next={next} />
              </div>
            ) : (
              <form method="post" action={devAction}>
                <Button type="submit" className="w-full" data-testid="dev-sign-in">
                  Continue
                </Button>
              </form>
            )}
          </div>
          <p className="mt-5 text-center text-xs text-white/50" data-testid="auth-footer">
            {footer}
          </p>
        </div>
      </div>
    </main>
  );
}
