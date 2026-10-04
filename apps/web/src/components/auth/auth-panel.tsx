import Link from "next/link";

import { SocialSignIn } from "@/components/auth/social-sign-in";
import { SiteLogo } from "@/components/site/Logo";
import { Button } from "@/components/ui/button";

/**
 * The shared shell behind `/sign-in` and `/sign-up`. Both pages post to the same Better Auth
 * endpoints — social sign-in creates the user on first use — so they differ only in wording.
 *
 * This stays a **server component**: the E2E suite clicks the sign-in button the moment the HTML
 * lands (see the note in `e2e/tests/helpers.ts`), so the card must be server-rendered and must
 * never wait on the client. It has no client leaf at all now — the backdrop used to be
 * `AuthField`, a WebGL mesh gradient in the old brand cyan, and it is two CSS gradients instead.
 * That deletes a shader, a canvas and a `"use client"` boundary from the critical path of the
 * one page a visitor cannot get past, and it removes the class of bug recorded in
 * `webgl-backdrop-swallows-clicks`.
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
    // No border under it: the marketing header is a transparent bar with a glass capsule in it,
    // and a hairline rule here would be the one place on the site where a header draws a line.
    <header className="absolute inset-x-0 top-0 z-20">
      <div className="mx-auto flex h-24 w-full max-w-7xl items-center justify-between gap-4 px-6">
        <Link href="/" aria-label="Calypr home" className="shrink-0">
          <SiteLogo className="h-6 w-auto" />
        </Link>
        {/* The same capsule the marketing header's CTA uses, down to the mono casing — this is
            the same site, and the page a visitor most needs to trust. */}
        <Link
          href={action.href}
          className="liquid-glass inline-flex items-center gap-2 rounded-full px-5 py-2 font-mono text-[11px] uppercase tracking-[0.14em] text-[var(--text-on-dark)] transition-colors duration-200 ease-[var(--ease-standard)] hover:bg-white/[0.08]"
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
      className="liquid-glass mb-4 w-full rounded-[18px] p-4 text-sm leading-relaxed text-[var(--text-on-dark-muted)] [--liquid-fill:0.05]"
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
    // The shadcn `Button` the provider rows are built from reads the global `--primary` (white),
    // so the sign-in buttons match every other primary action in the product.
    <main
      className="relative flex min-h-full flex-1 items-center justify-center overflow-hidden bg-[var(--ink-950)] p-6 text-[var(--text-on-dark)]"
    >
      {/* The ambient ground, matching the hero's: a wide off-white wash with a narrower, weaker
          green pass inside it, both originating above the top edge so what shows is the falloff
          rather than a clipped hotspot. Off-white and not green for the wide one — a green glow
          at this size tints the whole upper half and turns the card's own accents muddy. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[70vh] bg-[radial-gradient(85%_100%_at_50%_-8%,rgba(226,232,240,0.11)_0%,rgba(226,232,240,0.04)_40%,transparent_74%)]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-[56vh] bg-[radial-gradient(50%_100%_at_50%_-10%,rgba(92,201,155,0.04)_0%,rgba(92,201,155,0.015)_45%,transparent_78%)]"
      />
      <AuthNav action={navAction} />
      <div className="relative z-10 flex w-full max-w-sm flex-col items-center">
        {children}
        {error ? <Notice testId="auth-error-notice">{errorMessage(error)}</Notice> : null}

        {/* The card is the system's glass at panel density, with the accent glow the `Card`
            primitive's `featured` state uses — this is the one card on the page, so it gets the
            treatment reserved for the one card that matters. */}
        <div className="liquid-glass w-full rounded-[24px] p-7 shadow-[var(--glow-accent)] [--liquid-blur:14px] [--liquid-fill:0.06]">
          <h1 className="font-heading text-xl font-medium tracking-[-0.02em] text-[var(--text-on-dark)]">
            {title}
          </h1>
          <p className="mt-1.5 text-sm leading-relaxed text-[var(--text-on-dark-muted)]">
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
          <p
            className="mt-6 text-center text-xs leading-relaxed text-[var(--text-on-dark-faint)]"
            data-testid="auth-footer"
          >
            {footer}
          </p>
        </div>
      </div>
    </main>
  );
}
