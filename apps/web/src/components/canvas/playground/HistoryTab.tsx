"use client";

import { MoreHorizontal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
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
import { useToast } from "@/components/ui/toast";
import {
  type ConversationDetail,
  type ConversationSummary,
  deleteConversation,
  getConversation,
  listConversations,
  renameConversation,
} from "@/lib/api";
import { relativeTime } from "@/lib/time";

import { DeleteConfirm } from "./DeleteConfirm";

/** Past Playground conversations: search, reopen, rename, delete.
 *
 *  Search is **server-side** and debounced, unlike the dashboard's project filter. The dashboard
 *  already holds every project in memory; this list doesn't, so filtering client-side would
 *  search the page you happen to be looking at and silently miss the rest. */
export function HistoryTab({
  agentId,
  scopeReady,
  activeId,
  onOpen,
  onDeleted,
}: {
  /** The project whose conversations to show. Undefined means this canvas isn't saved yet, and
   *  the list scopes to conversations belonging to no project (`agent_id=none`) rather than to
   *  the whole workspace — otherwise every project shows every other project's chats. */
  agentId?: string;
  /** False while the canvas is still resolving `?agent=` from the URL. Fetching before that
   *  briefly lists the *unassigned* conversations for a project that does have an id, which
   *  looks exactly like the cross-project bleed this scoping exists to prevent. */
  scopeReady: boolean;
  activeId: string | null;
  onOpen: (detail: ConversationDetail) => void;
  /** The open conversation was deleted, so the chat panel has to let go of it. */
  onDeleted: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [items, setItems] = useState<ConversationSummary[] | null>(null);
  const [renaming, setRenaming] = useState<ConversationSummary | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    const id = setTimeout(() => setDebounced(query.trim()), 250);
    return () => clearTimeout(id);
  }, [query]);

  // A promise chain rather than an `async` body: the state lands in a callback, which is both
  // the idiom the dashboard list already uses and what keeps `react-hooks/set-state-in-effect`
  // able to see that nothing is set synchronously during the effect.
  const load = useCallback(() => {
    if (!scopeReady) return Promise.resolve();
    // `"none"` is the API's sentinel for "belongs to no project" — a scope a UUID can't express.
    return listConversations({ q: debounced, agentId: agentId ?? "none" })
      .then((page) => setItems(page.items))
      .catch(() => setItems([]));
  }, [debounced, agentId, scopeReady]);

  useEffect(() => {
    load();
  }, [load]);

  async function open(row: ConversationSummary) {
    const detail = await getConversation(row.id);
    if (!detail) {
      toast("That conversation is no longer available.", "error");
      void load();
      return;
    }
    onOpen(detail);
  }

  async function confirmRename() {
    if (!renaming) return;
    const title = renameValue.trim();
    if (!title) return;
    setBusy(true);
    const ok = await renameConversation(renaming.id, title);
    setBusy(false);
    if (!ok) {
      toast("Could not rename that conversation.", "error");
      return;
    }
    setRenaming(null);
    void load();
  }

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    const ok = await deleteConversation(deleting.id);
    setBusy(false);
    if (!ok) {
      toast("Could not delete that conversation.", "error");
      return;
    }
    onDeleted(deleting.id);
    setDeleting(null);
    void load();
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-3">
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search conversations…"
          data-testid="history-search"
        />
      </div>
      <div className="flex-1 overflow-auto p-2" data-testid="history-list">
        {items === null ? (
          <p className="p-2 text-sm text-muted-foreground">Loading…</p>
        ) : items.length === 0 ? (
          // Two distinct empty states: "you have none" and "none match" are different problems
          // and a single message would misdescribe one of them.
          <div className="m-1 rounded-lg border border-dashed border-border p-6 text-center">
            <p className="text-sm text-muted-foreground">
              {debounced ? "No matching conversations." : "No conversations in this project yet."}
            </p>
            {!debounced ? (
              // Say "this project", not just "here" — the list is scoped, so an empty History
              // next to a workspace full of chats needs to explain itself.
              <p className="mt-1 text-xs text-muted-foreground">
                Chats you have in this project&rsquo;s Playground are saved here.
              </p>
            ) : null}
          </div>
        ) : (
          items.map((c) => (
            <div
              key={c.id}
              data-testid="history-item"
              className={`group relative rounded-md px-2 py-2 hover:bg-muted ${
                c.id === activeId ? "bg-muted" : ""
              }`}
            >
              <button
                type="button"
                onClick={() => void open(c)}
                className="w-full pr-7 text-left"
              >
                <div className="truncate text-sm font-medium">{c.title || "Untitled chat"}</div>
                {c.preview ? (
                  <div className="mt-0.5 truncate text-xs text-muted-foreground">
                    {c.preview}
                  </div>
                ) : null}
                <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{relativeTime(c.updated_at)}</span>
                  <span>·</span>
                  <span>
                    {c.message_count} {c.message_count === 1 ? "message" : "messages"}
                  </span>
                  {!c.has_state ? (
                    // The transcript outlives the agent's memory of it. Saying so here is the
                    // difference between an explained limitation and an agent that seems broken.
                    <span
                      data-testid="history-expired"
                      title="The transcript is kept, but the agent no longer remembers this chat."
                      className="rounded border border-border px-1 py-px"
                    >
                      memory expired
                    </span>
                  ) : null}
                </div>
              </button>
              <div className="absolute top-2 right-1">
                <DropdownMenu>
                  <DropdownMenuTrigger
                    aria-label="Conversation actions"
                    data-testid="history-menu"
                    className="rounded-md p-1 text-muted-foreground opacity-0 transition hover:bg-background group-hover:opacity-100 data-[popup-open]:opacity-100"
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => void open(c)}>Open</DropdownMenuItem>
                    <DropdownMenuItem
                      data-testid="history-rename"
                      onClick={() => {
                        setRenameValue(c.title);
                        setRenaming(c);
                      }}
                    >
                      Rename
                    </DropdownMenuItem>
                    <DropdownMenuItem
                      variant="destructive"
                      data-testid="history-delete"
                      onClick={() => setDeleting(c)}
                    >
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            </div>
          ))
        )}
      </div>

      <Dialog open={renaming !== null} onOpenChange={(o) => !o && setRenaming(null)}>
        <DialogContent data-testid="history-rename-dialog">
          <DialogHeader>
            <DialogTitle>Rename conversation</DialogTitle>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && void confirmRename()}
            data-testid="history-rename-input"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenaming(null)}>
              Cancel
            </Button>
            <Button disabled={busy} onClick={() => void confirmRename()}>
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <DeleteConfirm
        open={deleting !== null}
        testId="history-delete-confirm"
        busy={busy}
        title="Delete conversation?"
        // Name the media count. Deleting a chat cascades to the files its runs generated, and a
        // dialog that stays silent about that turns a cascade into a nasty surprise.
        description={
          `“${deleting?.title || "Untitled chat"}” and its ${deleting?.message_count ?? 0} ` +
          "messages will be permanently deleted, along with any images or audio this " +
          "conversation generated. This can't be undone."
        }
        onConfirm={() => void confirmDelete()}
        onOpenChange={(o) => !o && setDeleting(null)}
      />
    </div>
  );
}
