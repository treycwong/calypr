import { cookies } from "next/headers";

import { SESSION_COOKIE } from "@/lib/constants";

export type Session = { userId: string };

/**
 * The single auth seam. Phase 0 reads a dev session cookie; to switch to Clerk
 * (org = tenant), reimplement this against Clerk and gate on CALYPR_AUTH_PROVIDER.
 * The rest of the app depends only on this function, never on the provider.
 */
export async function getSession(): Promise<Session | null> {
  const store = await cookies();
  const value = store.get(SESSION_COOKIE)?.value;
  return value ? { userId: value } : null;
}
