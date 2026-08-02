import { SettingsView } from "@/components/dashboard/settings-view";
import { getSession } from "@/lib/auth";

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
    />
  );
}
