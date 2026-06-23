import { cookies, headers } from "next/headers";

import { SESSION_COOKIE } from "@/lib/constants";

export type Session = { userId: string };

/**
 * Better Auth is active when a secret is configured (production); otherwise the app uses a
 * dev session cookie so it runs — and CI/E2E stay green — with no keys or database at all.
 * The rest of the app depends only on `getSession()`, never on the provider.
 */
export function betterAuthEnabled(): boolean {
  return !!process.env.BETTER_AUTH_SECRET;
}

export async function getSession(): Promise<Session | null> {
  if (betterAuthEnabled()) {
    // Imported lazily so the dev path never loads Better Auth's server runtime / pg.
    const { auth } = await import("@/lib/auth-server");
    const data = await auth.api.getSession({ headers: await headers() });
    return data?.user ? { userId: data.user.id } : null;
  }
  const store = await cookies();
  const value = store.get(SESSION_COOKIE)?.value;
  return value ? { userId: value } : null;
}
