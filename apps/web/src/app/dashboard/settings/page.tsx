import { SettingsView } from "@/components/dashboard/settings-view";
import { getSession } from "@/lib/auth";

export default async function SettingsPage() {
  const session = await getSession();
  if (!session) return null; // the dashboard layout already redirects unauthenticated users

  return (
    <SettingsView
      name={session.name}
      email={session.email}
      image={session.image}
    />
  );
}
