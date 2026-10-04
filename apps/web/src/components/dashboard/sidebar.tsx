"use client";

import { useState } from "react";
import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";
import {
  Check,
  ChevronsUpDown,
  Gauge,
  LayoutGrid,
  LayoutTemplate,
  Lock,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Settings,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { CalyprMark } from "@/components/brand/CalyprMark";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button, buttonVariants } from "@/components/ui/button";
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
import { SIDEBAR_COOKIE } from "@/lib/sidebar";
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
  defaultCollapsed = false,
}: {
  session: Session;
  /** Initial rail state, from `SIDEBAR_COOKIE`. */
  defaultCollapsed?: boolean;
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

  const [collapsed, setCollapsed] = useState(defaultCollapsed);
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

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    // A year; `lax` because it only ever needs to ride along with same-site navigations.
    document.cookie = `${SIDEBAR_COOKIE}=${next ? "1" : "0"}; path=/; max-age=31536000; samesite=lax`;
  }

  return (
    // A floating panel inset from the window edge (the layout supplies the gap), rather than a
    // full-height strip ruled off by a border — the shell reads as panels on a ground. Collapses
    // to a 60px icon rail; every label then moves into a tooltip so nothing is lost, only folded.
    <aside
      data-collapsed={collapsed ? "true" : "false"}
      className={cn(
        "flex shrink-0 flex-col overflow-hidden rounded-[16px] border border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width] duration-200 ease-[var(--ease-standard)]",
        collapsed ? "w-[60px]" : "w-60",
      )}
    >
      <TooltipPrimitive.Provider delay={200}>
        {/* Brand + workspace switcher. */}
        <div className={cn("flex items-center gap-1 p-2", collapsed && "flex-col")}>
          <DropdownMenu>
            <DropdownMenuTrigger
              data-testid="ws-switcher"
              aria-label="Switch workspace"
              className={cn(
                "flex min-w-0 items-center gap-2.5 rounded-[10px] p-1.5 text-left transition-colors hover:bg-white/[0.05] data-[popup-open]:bg-white/[0.06]",
                collapsed ? "justify-center" : "flex-1",
              )}
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px] bg-white text-[var(--ink-950)]">
                <CalyprMark className="h-4 w-4" />
              </span>
              {collapsed ? null : (
                <>
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium leading-tight tracking-tight">
                      Calypr
                    </span>
                    <span className="block truncate text-xs leading-tight text-muted-foreground">
                      {workspaceName}
                    </span>
                  </span>
                  <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                </>
              )}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-56">
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
          <RailTip label={collapsed ? "Expand sidebar" : "Collapse sidebar"} show>
            <button
              type="button"
              onClick={toggleCollapsed}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!collapsed}
              data-testid="sidebar-toggle"
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[9px] text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
            >
              {collapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </button>
          </RailTip>
        </div>

        {/* The one primary action in the shell. `/dashboard/new` owns the cap check (it shows the
            upgrade dialog on a refusal), so this needs no plan logic of its own. */}
        <div className="px-2 pb-2">
          <RailTip label="New project" show={collapsed}>
            <Link
              href="/dashboard/new"
              data-testid="sidebar-new-project"
              aria-label="New project"
              className={cn(
                buttonVariants({ size: "default" }),
                "h-9 w-full rounded-full",
                collapsed && "px-0",
              )}
            >
              <Plus className="h-4 w-4" />
              {collapsed ? null : "New project"}
            </Link>
          </RailTip>
        </div>

        <nav className="flex-1 space-y-0.5 px-2 py-2">
          {collapsed ? null : (
            <div className="px-3 pb-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-on-dark-faint)]">
              Workspace
            </div>
          )}
          {NAV.map((item) => {
            const active =
              item.href === "/dashboard"
                ? pathname === "/dashboard"
                : pathname.startsWith(item.href);
            return (
              <RailTip key={item.href} label={item.label} show={collapsed}>
                <Link
                  href={item.href}
                  data-testid={`nav-${item.label.toLowerCase()}`}
                  aria-label={collapsed ? item.label : undefined}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex h-9 items-center gap-2.5 rounded-full text-sm transition-colors",
                    collapsed ? "justify-center px-0" : "px-3",
                    active
                      ? "bg-sidebar-accent font-medium text-foreground"
                      : "text-muted-foreground hover:bg-white/[0.04] hover:text-foreground",
                  )}
                >
                  <item.icon className={cn("h-4 w-4 shrink-0", active ? "opacity-100" : "opacity-80")} />
                  {collapsed ? null : item.label}
                </Link>
              </RailTip>
            );
          })}
        </nav>

        {/* Account: one row that opens a menu, instead of a name block plus a full-width button. */}
        <div className="border-t border-sidebar-border p-2">
          <DropdownMenu>
            <DropdownMenuTrigger
              data-testid="user-menu"
              aria-label="Account menu"
              className={cn(
                "flex w-full items-center gap-2.5 rounded-[10px] p-1.5 text-left transition-colors hover:bg-white/[0.05] data-[popup-open]:bg-white/[0.06]",
                collapsed && "justify-center",
              )}
            >
              <Avatar className="h-7 w-7 shrink-0">
                {session.image ? <AvatarImage src={session.image} alt="" /> : null}
                <AvatarFallback className="text-[10px]">{initials}</AvatarFallback>
              </Avatar>
              {collapsed ? null : (
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium leading-tight">
                    {session.name}
                  </span>
                  <span className="block truncate text-xs leading-tight text-muted-foreground">
                    {session.email}
                  </span>
                </span>
              )}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" side="top" className="w-56">
              <DropdownMenuItem onClick={() => router.push("/dashboard/settings")}>
                <Settings className="h-3.5 w-3.5" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={signOut} data-testid="sign-out">
                <LogOut className="h-3.5 w-3.5" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </TooltipPrimitive.Provider>

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
            <p className="text-xs text-state-warning" data-testid="ws-new-error">
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

/**
 * Names a rail item when its label is folded away. `show={false}` renders the child untouched, so
 * the expanded sidebar carries no tooltip machinery at all. Uses the primitive's `render` prop so
 * the trigger *is* the link or button — `components/ui/tooltip` always renders its own `<button>`,
 * which would nest an anchor inside a button here.
 */
function RailTip({
  label,
  show,
  children,
}: {
  label: string;
  show: boolean;
  children: React.ReactElement;
}) {
  if (!show) return children;
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger render={children} />
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Positioner side="right" sideOffset={10} collisionPadding={8}>
          <TooltipPrimitive.Popup className="z-50 rounded-md bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-[0_16px_40px_-12px_rgba(0,0,0,0.65)] ring-1 ring-white/[0.08] duration-100 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0">
            {label}
          </TooltipPrimitive.Popup>
        </TooltipPrimitive.Positioner>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
