"use client";

import { Lock, MoreHorizontal, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
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
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  type AgentSummary,
  deleteAgent,
  listAgents,
  listWorkspaces,
  updateAgent,
  type WorkspaceList,
} from "@/lib/api";
import { ProjectArt } from "@/components/dashboard/ProjectArt";
import { LockedBanner } from "@/components/dashboard/locked-banner";
import { relativeTime } from "@/lib/time";

export default function ProjectsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<AgentSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [renaming, setRenaming] = useState<AgentSummary | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleting, setDeleting] = useState<AgentSummary | null>(null);
  // Only this page needs it, so it isn't paid for on every dashboard route: the switcher's list
  // carries `locked` and the plan, which is everything the banner has to say.
  const [ws, setWs] = useState<WorkspaceList | null>(null);

  const load = () =>
    listAgents()
      .then(setAgents)
      .catch(() => setAgents([]));
  useEffect(() => {
    load();
    listWorkspaces()
      .then(setWs)
      .catch(() => setWs(null));
  }, []);

  const filtered = (agents ?? []).filter((a) =>
    a.name.toLowerCase().includes(query.toLowerCase()),
  );

  async function doRename() {
    if (!renaming) return;
    await updateAgent(renaming.id, { name: renameValue.trim() || renaming.name });
    setRenaming(null);
    load();
  }
  async function doDelete() {
    if (!deleting) return;
    await deleteAgent(deleting.id);
    setDeleting(null);
    load();
  }

  return (
    // Full width with matching side padding. `max-w-5xl` capped the content at 1024px, which on
    // anything wider left the grid hugging the sidebar with a growing empty gutter on the right —
    // the page looked mis-aligned rather than centred.
    <div className="w-full px-10 py-8">
      <header className="flex items-center justify-between gap-4">
        <h1 className="font-heading text-2xl">Projects</h1>
        <div className="flex items-center gap-2">
          <Input
            placeholder="Search projects…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-48"
            data-testid="project-search"
          />
          <Link
            href="/dashboard/new"
            className={buttonVariants({ size: "sm" })}
            data-testid="new-project"
          >
            <Plus className="h-4 w-4" /> New Project
          </Link>
        </div>
      </header>

      <div className="mt-6">
        {/* Counts the *whole* account, not the filtered view — a search that hides every locked
            project must not make the banner claim there are none. */}
        <LockedBanner
          workspaces={(ws?.workspaces ?? []).filter((w) => w.locked).length}
          projects={(agents ?? []).filter((a) => a.locked).length}
          plan={ws?.plan ?? "free"}
        />
        {agents === null ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : filtered.length === 0 ? (
          <div
            className="dotted flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-16 text-center"
            data-testid="projects-empty"
          >
            <p className="text-sm font-medium">
              {(agents ?? []).length === 0 ? "No projects yet" : "No matches"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Start from a blank canvas or a template.
            </p>
            <Link
              href="/dashboard/new"
              className={`mt-4 ${buttonVariants({ size: "sm" })}`}
            >
              <Plus className="h-4 w-4" /> New Project
            </Link>
          </div>
        ) : (
          <div
            // More columns as the page widens, now that it uses the full width — three square
            // cards stretched across a large monitor would be posters, not thumbnails.
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5"
            data-testid="project-grid"
          >
            {filtered.map((a) => (
              <div
                key={a.id}
                className="group relative"
                data-testid="project-card"
                data-locked={a.locked ? "true" : "false"}
              >
                {/* Locked projects still open. You can read them, copy out of them, and delete
                    them — locking takes back capacity, not access. */}
                <Link href={`/canvas?agent=${a.id}`} className="block">
                  {/* Generative art keyed to the project id, not a drawing of its graph: most
                      graphs are a short line of dots, so drawing them made every card look the
                      same. This carries no information, which is exactly what frees it to be
                      distinctive enough to find a project by. */}
                  <div className="aspect-square overflow-hidden rounded-lg border border-border transition group-hover:border-foreground/20">
                    <ProjectArt seed={a.id} />
                  </div>
                  <div className="mt-2 flex items-center gap-1.5 pr-6">
                    <span className="truncate text-sm font-medium">{a.name}</span>
                    {a.locked ? (
                      <span
                        className="flex shrink-0 items-center gap-1 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground"
                        title="Read-only — over your plan's project limit"
                      >
                        <Lock className="h-2.5 w-2.5" />
                        Read-only
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    Edited {relativeTime(a.updated_at)}
                  </div>
                </Link>
                <div className="absolute top-2 right-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      aria-label="Project actions"
                      data-testid="project-menu"
                      className="rounded-md bg-background/80 p-1 text-muted-foreground opacity-0 transition hover:bg-muted group-hover:opacity-100 data-[popup-open]:opacity-100"
                    >
                      <MoreHorizontal className="h-4 w-4" />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => router.push(`/canvas?agent=${a.id}`)}
                      >
                        Open
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        data-testid="project-rename"
                        disabled={a.locked}
                        onClick={() => {
                          setRenameValue(a.name);
                          setRenaming(a);
                        }}
                      >
                        Rename
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        variant="destructive"
                        data-testid="project-delete"
                        onClick={() => setDeleting(a)}
                      >
                        Delete
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <Dialog
        open={!!renaming}
        onOpenChange={(o) => {
          if (!o) setRenaming(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename project</DialogTitle>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            data-testid="rename-input"
          />
          <DialogFooter>
            <DialogClose render={<Button variant="outline">Cancel</Button>} />
            <Button onClick={doRename} data-testid="rename-save">
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!deleting}
        onOpenChange={(o) => {
          if (!o) setDeleting(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete project?</DialogTitle>
            <DialogDescription>
              “{deleting?.name}” will be permanently deleted. This can’t be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline">Cancel</Button>} />
            <Button
              variant="destructive"
              onClick={doDelete}
              data-testid="delete-confirm"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
