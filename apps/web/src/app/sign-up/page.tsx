import Link from "next/link";

import { AuthPanel } from "@/components/auth/auth-panel";
import { betterAuthEnabled } from "@/lib/auth";

type Props = { searchParams: Promise<{ next?: string; error?: string }> };

export const metadata = {
  title: "Create your Calypr account",
  description: "Sign up for Calypr and turn a prompt into a working agent.",
};

/**
 * Mechanically identical to `/sign-in` — social sign-in creates the user on first use, so there
 * is no separate signup exchange. It exists as its own route so the heading, the copy and the
 * URL can speak to someone who has never been here before.
 */
export default async function SignUpPage({ searchParams }: Props) {
  const { next, error } = await searchParams;

  return (
    <AuthPanel
      title="Create your Calypr account"
      subtitle="Start building agents in minutes. No credit card."
      next={next}
      enabled={betterAuthEnabled()}
      error={error}
      navAction={{ label: "Log in", href: "/sign-in" }}
      footer={
        <>
          Already have an account?{" "}
          <Link href="/sign-in" className="text-white/80 underline underline-offset-4">
            Log in
          </Link>
        </>
      }
    />
  );
}
