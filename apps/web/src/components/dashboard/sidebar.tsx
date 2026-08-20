"use client";

import { useState } from "react";
import {
  Check,
  ChevronsUpDown,
  Gauge,
  LayoutGrid,
  LayoutTemplate,
  Lock,
  Plus,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  CapReachedError,
  createWorkspace,
  switchWorkspace,
  type WorkspaceSummary,
} from "@/lib/api";
import type { Session } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/dashboard", label: "Projects", icon: LayoutGrid },
  { href: "/dashboard/workflows", label: "Workflows", icon: LayoutTemplate },
  { href: "/dashboard/usage", label: "Usage", icon: Gauge },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
] as const;

export function Sidebar({
  session,
  betterAuth,
  workspaces = [],
  canCreateWorkspace = false,
}: {
  session: Session;
  betterAuth: boolean;
  workspaces?: WorkspaceSummary[];
  /** Whether this account's plan has room for another workspace. Decided by the API from
   *  `entitlements.LIMITS` — never re-derived here from a plan name. */
  canCreateWorkspace?: boolean;
}) {
  // The list already says which one the request resolved to. That's the *resolved* workspace,
  // not what the cookie asked for, so a stale or foreign cookie self-corrects on the next paint.
  const current = workspaces.find((w) => w.is_current) ?? null;
  const pathname = usePathname();
  const router = useRouter();
  const initials = (session.name || session.email || "U").slice(0, 2).toUpperCase();

  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [createError, setCreateError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signOut() {
    // Clear the workspace cookie too: the next person to sign in on this machine would
    // otherwise send someone else's workspace id. The API rejects it, but they'd land on a
    // confusing first paint before it self-corrected.
    await switchWorkspace().catch(() => {});
    if (betterAuth) {
      const { authClient } = await import("@/lib/auth-client");
      await authClient.signOut().catch(() => {});
    } else {
      await fetch("/api/auth/signout", { method: "POST" }).catch(() => {});
    }
    window.location.href = "/sign-in";
  }

  async function selectWorkspace(id: string) {
    if (id === current?.id) return;
    await switchWorkspace(id);
    // Leave any page scoped to a single agent — that agent belongs to the workspace we just
    // left, so staying would 404 the moment the shell re-renders.
    if (pathname !== "/dashboard") router.push("/dashboard");
    // Re-renders the shell (a server component reading the cookie) with the new workspace. It
    // does *not* reset the client pages beneath — `router.refresh()` preserves client state, so
    // a page that fetched on mount would keep showing the workspace we just left. The layout
    // keys `<main>` on the resolved workspace id to force that remount; see the comment there.
    router.refresh();
  }

  async function submitNewWorkspace() {
    const name = newName.trim();
    if (!name || busy) return;
    setBusy(true);
    setCreateError(null);
    try {
      const created = await createWorkspace(name);
      setCreating(false);
      setNewName("");
      await selectWorkspace(created.id);
    } catch (err) {
      // A cap is an expected answer, not a failure — show what they ran out of, in place.
      setCreateError(
        err instanceof CapReachedError ? err.message : "Could not create that workspace.",
      );
    } finally {
      setBusy(false);
    }
  }

  const workspaceName = current?.name ?? "Workspace";

  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-card/30">
      <div className="flex h-14 items-center px-2">
        <DropdownMenu>
          <DropdownMenuTrigger
            data-testid="ws-switcher"
            aria-label="Switch workspace"
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted/50 data-[popup-open]:bg-muted"
          >
            <div className="min-w-0 flex-1">
              <div className="font-sans text-sm font-semibold tracking-tight">calypr</div>
              <div className="truncate text-xs text-muted-foreground">{workspaceName}</div>
            </div>
            <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-52">
            {workspaces.map((ws) => (
              // A locked workspace stays selectable: you can still open it, read it, and delete
              // it — that's the point of locking rather than hiding. The badge says why nothing
              // in it will save.
              <DropdownMenuItem
                key={ws.id}
                data-testid={`ws-option-${ws.id}`}
                data-locked={ws.locked ? "true" : "false"}
                onClick={() => selectWorkspace(ws.id)}
              >
                <span className="min-w-0 flex-1 truncate">{ws.name}</span>
                {ws.locked ? (
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Lock className="h-3 w-3" />
                    Read-only
                  </span>
                ) : null}
                {ws.id === current?.id ? <Check className="h-3.5 w-3.5" /> : null}
              </DropdownMenuItem>
            ))}
            {/* Both entries below are workspace *management*, and on a plan capped at one
                workspace there is nothing to manage from here: 'New workspace' could only ever
                lead to an upsell dead end, and the settings tab it points at is one click away
                under Settings anyway. Upgrading is surfaced on the Settings → Billing tab, so
                nothing is lost by keeping this menu to the switching it is for. */}
            {canCreateWorkspace ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  data-testid="ws-new"
                  onClick={() => {
                    setCreateError(null);
                    setNewName("");
                    setCreating(true);
                  }}
                >
                  <Plus className="h-3.5 w-3.5" />
                  New workspace
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => router.push("/dashboard/settings?tab=workspace")}>
                  Workspace settings
                </DropdownMenuItem>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>
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

      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New workspace</DialogTitle>
            <DialogDescription>
              A separate set of projects. Your plan&rsquo;s projects, credits and storage are
              shared across all of your workspaces.
            </DialogDescription>
          </DialogHeader>
          <Input
            autoFocus
            value={newName}
            data-testid="ws-new-name"
            placeholder="Client work"
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submitNewWorkspace();
            }}
          />
          {createError ? (
            <p className="text-xs text-amber-600 dark:text-amber-500" data-testid="ws-new-error">
              {createError}{" "}
              <Link href="/pricing" className="underline">
                See plans
              </Link>
            </p>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreating(false)}>
              Cancel
            </Button>
            <Button
              onClick={submitNewWorkspace}
              disabled={!newName.trim() || busy}
              data-testid="ws-new-submit"
            >
              {busy ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </aside>
  );
}
