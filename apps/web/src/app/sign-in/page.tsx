import Link from "next/link";

import { AuthPanel } from "@/components/auth/auth-panel";
import { betterAuthEnabled } from "@/lib/auth";

type Props = {
  searchParams: Promise<{ next?: string; deleted?: string; error?: string }>;
};

export default async function SignInPage({ searchParams }: Props) {
  const { next, deleted, error } = await searchParams;

  return (
    <AuthPanel
      title="Log in to Calypr"
      subtitle="Welcome back. Continue with the account you signed up with."
      next={next}
      enabled={betterAuthEnabled()}
      error={error}
      navAction={{ label: "Sign up", href: "/sign-up" }}
      footer={
        <>
          New here?{" "}
          <Link href="/sign-up" className="font-medium text-[var(--text-on-dark)] underline underline-offset-4">
            Create an account
          </Link>
        </>
      }
    >
      {/* The only confirmation a deleted account ever gets: by this point there is no session
          to show a message in, and no address we're willing to keep in order to email one. */}
      {deleted !== undefined ? (
        <div
          className="liquid-glass mb-4 w-full rounded-[18px] p-4 text-sm leading-relaxed text-[var(--text-on-dark-muted)] [--liquid-fill:0.05]"
          data-testid="account-deleted-notice"
        >
          Your account has been deleted. Signing in again will start a new one.
        </div>
      ) : null}
    </AuthPanel>
  );
}
