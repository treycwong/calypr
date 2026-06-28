import { cookies, headers } from "next/headers";

import { SESSION_COOKIE } from "@/lib/constants";

export type Session = {
  userId: string;
  name: string;
  email: string;
  image: string | null;
};

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
    if (!data?.user) return null;
    return {
      userId: data.user.id,
      name: data.user.name ?? "",
      email: data.user.email ?? "",
      image: data.user.image ?? null,
    };
  }
  const store = await cookies();
  const value = store.get(SESSION_COOKIE)?.value;
  if (!value) return null;
  // Dev session: no real profile — synthesize a placeholder so the UI renders.
  return { userId: value, name: "Developer", email: "dev@calypr.local", image: null };
}
