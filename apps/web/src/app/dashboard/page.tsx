"use client";

import { MoreHorizontal, Plus } from "lucide-react";
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
import { type AgentSummary, deleteAgent, listAgents, updateAgent } from "@/lib/api";

function relativeTime(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const m = Math.floor(seconds / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

export default function ProjectsPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<AgentSummary[] | null>(null);
  const [query, setQuery] = useState("");
  const [renaming, setRenaming] = useState<AgentSummary | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleting, setDeleting] = useState<AgentSummary | null>(null);

  const load = () =>
    listAgents()
      .then(setAgents)
      .catch(() => setAgents([]));
  useEffect(() => {
    load();
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
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Projects</h1>
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
            className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
            data-testid="project-grid"
          >
            {filtered.map((a) => (
              <div
                key={a.id}
                className="group relative rounded-lg border border-border bg-card p-4 transition hover:border-foreground/20"
                data-testid="project-card"
              >
                <Link href={`/canvas?agent=${a.id}`} className="block">
                  <div className="truncate pr-6 text-sm font-medium">{a.name}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    Edited {relativeTime(a.updated_at)}
                  </div>
                </Link>
                <div className="absolute top-2 right-2">
                  <DropdownMenu>
                    <DropdownMenuTrigger
                      aria-label="Project actions"
                      data-testid="project-menu"
                      className="rounded-md p-1 text-muted-foreground opacity-0 transition hover:bg-muted group-hover:opacity-100 data-[popup-open]:opacity-100"
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
