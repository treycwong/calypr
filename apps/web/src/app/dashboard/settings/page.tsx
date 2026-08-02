import { SettingsView } from "@/components/dashboard/settings-view";
import { getSession } from "@/lib/auth";

export default async function SettingsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const session = await getSession();
  if (!session) return null; // the dashboard layout already redirects unauthenticated users

  // Land on the Billing tab when returning from Stripe Checkout (`?upgraded=1`) or the Customer
  // Portal (`?tab=billing`). Resolved server-side so the client renders the right tab on first
  // paint — no post-mount switch, no hydration mismatch.
  const params = await searchParams;
  const initialTab =
    params.tab === "billing" || params.upgraded !== undefined ? "billing" : "account";

  return (
    <SettingsView
      name={session.name}
      email={session.email}
      image={session.image}
      initialTab={initialTab}
    />
  );
}
