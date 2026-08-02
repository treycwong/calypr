import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { Sidebar } from "@/components/dashboard/sidebar";
import { fetchCurrentWorkspace, fetchWorkspaces } from "@/lib/api-server";
import { betterAuthEnabled, getSession } from "@/lib/auth";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  // Middleware already gates /dashboard/*; this also gives the shell the session to render.
  const session = await getSession();
  if (!session) redirect("/sign-in?next=/dashboard");

  // Fetched here rather than in the client sidebar for two reasons: it avoids a waterfall on
  // every dashboard page, and it means the workspace name is correct on first paint instead of
  // flashing the wrong one. This layout re-renders on `router.refresh()`, which is exactly what
  // the switcher triggers after setting the cookie.
  const [workspaces, current] = await Promise.all([
    fetchWorkspaces(),
    fetchCurrentWorkspace(),
  ]);

  return (
    <div className="flex h-screen">
      <Sidebar
        session={session}
        betterAuth={betterAuthEnabled()}
        workspaces={workspaces}
        current={current}
      />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
