import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { Sidebar } from "@/components/dashboard/sidebar";
import { fetchWorkspaces } from "@/lib/api-server";
import { betterAuthEnabled, getSession } from "@/lib/auth";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  // Middleware already gates /dashboard/*; this also gives the shell the session to render.
  const session = await getSession();
  if (!session) redirect("/sign-in?next=/dashboard");

  // The list only — deliberately not `/workspaces/current` as well. That endpoint summarises
  // credits (which can *write* a lazy grant) and counts projects and workspaces, and this layout
  // renders on every page under /dashboard; paying for all of it on each navigation to render a
  // name in the sidebar is the wrong trade. Everything the switcher needs — names, ids, which
  // one is current — is already in the list. Pages that want usage fetch it themselves.
  //
  // Fetched server-side rather than in the client sidebar so the workspace name is right on
  // first paint instead of flashing. The layout re-renders on `router.refresh()`, which is what
  // the switcher triggers after setting the cookie.
  // Carries `can_create` alongside the rows, so the switcher can offer the right affordance on
  // first paint without a second request — see `WorkspaceList` in the API schemas.
  const { workspaces, can_create } = await fetchWorkspaces();

  return (
    <div className="flex h-screen">
      <Sidebar
        session={session}
        betterAuth={betterAuthEnabled()}
        workspaces={workspaces}
        canCreateWorkspace={can_create}
      />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
