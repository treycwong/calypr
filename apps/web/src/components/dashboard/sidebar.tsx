"use client";

import { LayoutGrid, Settings } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import type { Session } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Projects", icon: LayoutGrid },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar({
  session,
  betterAuth,
}: {
  session: Session;
  betterAuth: boolean;
}) {
  const pathname = usePathname();
  const initials = (session.name || session.email || "U").slice(0, 2).toUpperCase();

  async function signOut() {
    if (betterAuth) {
      const { authClient } = await import("@/lib/auth-client");
      await authClient.signOut().catch(() => {});
    } else {
      await fetch("/api/auth/signout", { method: "POST" }).catch(() => {});
    }
    window.location.href = "/sign-in";
  }

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-card/30">
      <div className="flex h-14 items-center px-4">
        <Link href="/dashboard" className="font-mono text-sm font-semibold tracking-tight">
          calypr
        </Link>
      </div>
      <nav className="flex-1 space-y-1 px-2 py-2">
        {NAV.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              data-testid={`nav-${item.label.toLowerCase()}`}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-muted font-medium text-foreground"
                  : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2">
          <Avatar className="h-7 w-7">
            {session.image ? <AvatarImage src={session.image} alt="" /> : null}
            <AvatarFallback className="text-xs">{initials}</AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">{session.name}</div>
            <div className="truncate text-xs text-muted-foreground">{session.email}</div>
          </div>
        </div>
        <Button
          variant="outline"
          size="sm"
          className="mt-2 w-full"
          onClick={signOut}
          data-testid="sign-out"
        >
          Sign out
        </Button>
      </div>
    </aside>
  );
}
