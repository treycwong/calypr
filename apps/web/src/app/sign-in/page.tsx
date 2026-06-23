import Link from "next/link";

import { GithubSignIn } from "@/components/auth/github-sign-in";
import { Button } from "@/components/ui/button";
import { betterAuthEnabled } from "@/lib/auth";

type Props = { searchParams: Promise<{ next?: string }> };

function Frame({ children }: { children: React.ReactNode }) {
  return (
    <main className="dotted relative flex min-h-full flex-1 items-center justify-center p-6">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(55%_45%_at_50%_30%,rgba(255,255,255,0.05),transparent)]"
      />
      <div className="relative flex w-full max-w-sm flex-col items-center">
        <Link href="/" className="mb-8 flex items-center gap-2">
          <svg width="22" height="22" viewBox="0 0 20 20" aria-hidden className="text-foreground">
            <line x1="5" y1="5" x2="5" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
            <line x1="5" y1="5" x2="15" y2="15" stroke="currentColor" strokeWidth="1" opacity="0.4" />
            <circle cx="5" cy="5" r="2.4" fill="currentColor" />
            <circle cx="5" cy="15" r="2.4" fill="currentColor" opacity="0.55" />
            <circle cx="15" cy="15" r="2.4" fill="currentColor" opacity="0.8" />
          </svg>
          <span className="font-mono text-sm font-medium tracking-tight">calypr</span>
        </Link>
        {children}
      </div>
    </main>
  );
}

export default async function SignInPage({ searchParams }: Props) {
  const { next } = await searchParams;
  const enabled = betterAuthEnabled();
  const devAction = `/api/auth/dev${next ? `?next=${encodeURIComponent(next)}` : ""}`;

  return (
    <Frame>
      <div className="w-full rounded-xl border border-border bg-card/40 p-6 backdrop-blur">
        <h1 className="text-lg font-medium tracking-tight">Sign in to Calypr</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {enabled
            ? "Continue with your GitHub account."
            : "Development sign-in — set Better Auth keys to enable real auth."}
        </p>
        <div className="mt-5">
          {enabled ? (
            <GithubSignIn next={next} />
          ) : (
            <form method="post" action={devAction}>
              <Button type="submit" className="w-full" data-testid="dev-sign-in">
                Continue
              </Button>
            </form>
          )}
        </div>
      </div>
      <p className="mt-6 font-mono text-[11px] text-muted-foreground">prompt → canvas → code</p>
    </Frame>
  );
}
