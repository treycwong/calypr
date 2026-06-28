import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { Sidebar } from "@/components/dashboard/sidebar";
import { betterAuthEnabled, getSession } from "@/lib/auth";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  // Middleware already gates /dashboard/*; this also gives the shell the session to render.
  const session = await getSession();
  if (!session) redirect("/sign-in?next=/dashboard");

  return (
    <div className="flex h-screen">
      <Sidebar session={session} betterAuth={betterAuthEnabled()} />
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  );
}
