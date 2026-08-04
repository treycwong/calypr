import { headers } from "next/headers";

import { SettingsView } from "@/components/dashboard/settings-view";
import { betterAuthEnabled, getSession } from "@/lib/auth";

/**
 * Which social providers this user has linked.
 *
 * Resolved here rather than from the browser so the Integrations card renders correctly on
 * first paint — a client round-trip would flash "not connected" at someone who is, which reads
 * as an error rather than a loading state. Returns `[]` in dev (no Better Auth) and on failure:
 * "we couldn't tell" and "not connected" look the same, and the card is read-only either way.
 */
async function linkedProviders(): Promise<string[]> {
  if (!betterAuthEnabled()) return [];
  try {
    const { auth } = await import("@/lib/auth-server");
    const accounts = await auth.api.listUserAccounts({ headers: await headers() });
    return (accounts ?? []).map((a: { providerId: string }) => a.providerId);
  } catch {
    return [];
  }
}

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await getSession();
  if (!session) return null; // the dashboard layout already redirects unauthenticated users

  // Land on the right tab when arriving with one named: `?upgraded=1` returning from Stripe
  // Checkout, `?tab=billing` from the Customer Portal, `?tab=workspace` from the sidebar's
  // workspace switcher. Resolved server-side so the client renders the right tab on first paint
  // — no post-mount switch, no hydration mismatch.
  const params = await searchParams;
  const requested = typeof params.tab === "string" ? params.tab : "";
  const initialTab =
    params.upgraded !== undefined
      ? "billing"
      : ["billing", "workspace", "account"].includes(requested)
        ? requested
        : "account";

  return (
    <SettingsView
      name={session.name}
      email={session.email}
      image={session.image}
      initialTab={initialTab}
      // Whether a profile edit can actually persist. The dev path synthesizes its session from
      // a cookie and has **no profile store at all**, so saving there would appear to work and
      // silently revert on reload — worse than a disabled field that explains itself.
      manageable={betterAuthEnabled()}
      providers={await linkedProviders()}
    />
  );
}
