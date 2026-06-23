import { cookies } from "next/headers";

import { SESSION_COOKIE } from "@/lib/constants";

export type Session = { userId: string };

/**
 * Clerk is active when a publishable key is configured (production); otherwise the app
 * uses a dev session cookie so it runs — and CI/E2E stay green — with no keys at all.
 * The rest of the app depends only on `getSession()`, never on the provider.
 */
export function clerkEnabled(): boolean {
  return !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
}

export async function getSession(): Promise<Session | null> {
  if (clerkEnabled()) {
    // Imported lazily so the dev path never loads Clerk's server runtime.
    const { auth } = await import("@clerk/nextjs/server");
    const { userId } = await auth();
    return userId ? { userId } : null;
  }
  const store = await cookies();
  const value = store.get(SESSION_COOKIE)?.value;
  return value ? { userId: value } : null;
}
