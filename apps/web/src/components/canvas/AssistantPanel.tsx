"use client";

import type { GraphSpec } from "@calypr/dsl";
import type { Edge, Node } from "@xyflow/react";
import { Check, Loader2, RotateCcw, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { track } from "@/lib/analytics";
import { assistAgent } from "@/lib/api";
import type { NodeData } from "@/lib/graph";

/** A snapshot of the canvas taken just before a proposed graph is previewed (single-level undo). */
export type CanvasSnapshot = {
  nodes: Node<NodeData>[];
  edges: Edge[];
  name: string;
};

export type AssistantPanelProps = {
  /** Current canvas as a spec for refine mode, or null when the canvas is empty. */
  getCurrentGraph: () => GraphSpec | null;
  /** Grab the current canvas so it can be restored after a preview. */
  snapshot: () => CanvasSnapshot;
  /** Show a graph on the canvas (used for both preview and commit). */
  applyGraph: (spec: GraphSpec) => void;
  /** Put a previously-captured snapshot back on the canvas. */
  restore: (snap: CanvasSnapshot) => void;
};

/** Lifecycle of a proposed graph: shown live on the canvas, then kept or dropped. */
type ProposalState = "preview" | "applied" | "inactive";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: boolean; // assistant is still streaming
  error?: boolean;
  // Set when the draft ran on the fallback model because the chosen one needed a BYO key.
  notice?: string;
  spec?: GraphSpec; // the proposed graph
  proposal?: ProposalState;
  snapshot?: CanvasSnapshot; // canvas state captured before previewing
};

let _id = 0;
const nextId = () => `m${++_id}`;

function nodeSummary(spec: GraphSpec): string {
  const nodes = spec.nodes ?? [];
  const edges = spec.edges ?? [];
  return `${nodes.length} node${nodes.length === 1 ? "" : "s"} · ${edges.length} edge${
    edges.length === 1 ? "" : "s"
  }`;
}

export function AssistantPanel({
  getCurrentGraph,
  snapshot,
  applyGraph,
  restore,
}: AssistantPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const patch = useCallback((id: string, next: Partial<ChatMessage>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...next } : m)));
  }, []);

  const scrollToEnd = useCallback(() => {
    requestAnimationFrame(() =>
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }),
    );
  }, []);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;

    const history = [
      ...messages
        .filter((m) => m.content && !m.error)
        .map((m) => ({ role: m.role, content: m.content })),
      { role: "user" as const, content: text },
    ];
    const userMsg: ChatMessage = { id: nextId(), role: "user", content: text };
    const botId = nextId();
    setMessages((prev) => [
      ...prev,
      userMsg,
      { id: botId, role: "assistant", content: "", thinking: true },
    ]);
    setInput("");
    setBusy(true);
    track("assistant_prompted", { chars: text.length });

    const current = getCurrentGraph();
    try {
      for await (const ev of assistAgent(history, current)) {
        if (ev.type === "notice") {
          // Held separately from `content`: the `note` event below replaces content wholesale,
          // and the substitution warning must survive that.
          patch(botId, { notice: ev.message });
          track("assistant_model_substituted");
        } else if (ev.type === "note") {
          patch(botId, { content: ev.text });
        } else if (ev.type === "graph") {
          // Preview immediately on the canvas so the user sees the change before approving;
          // snapshot first so Discard/Undo restores exactly what was there.
          const snap = snapshot();
          applyGraph(ev.spec);
          patch(botId, { spec: ev.spec, snapshot: snap, proposal: "preview" });
        } else if (ev.type === "error") {
          patch(botId, {
            thinking: false,
            error: true,
            content: ev.message || "The assistant hit a problem. Please try again.",
          });
          track("assistant_error", { message: ev.message });
        }
        // `status` events just keep the shimmer alive; nothing to render per-phase.
      }
    } catch {
      patch(botId, {
        thinking: false,
        error: true,
        content: "The assistant is unavailable right now.",
      });
      track("assistant_error", { message: "stream failed" });
    } finally {
      patch(botId, { thinking: false });
      setBusy(false);
      scrollToEnd();
    }
  }, [input, busy, messages, getCurrentGraph, snapshot, applyGraph, patch, scrollToEnd]);

  const onApply = useCallback(
    (m: ChatMessage) => {
      if (!m.spec) return;
      // Already on the canvas from the preview — just commit.
      patch(m.id, { proposal: "applied" });
      track("assistant_graph_applied", {
        nodes: m.spec.nodes?.length ?? 0,
        edges: m.spec.edges?.length ?? 0,
      });
    },
    [patch],
  );

  const onRevert = useCallback(
    (m: ChatMessage) => {
      if (m.snapshot) restore(m.snapshot);
      patch(m.id, { proposal: "inactive" });
      track("assistant_restore");
    },
    [restore, patch],
  );

  const onReapply = useCallback(
    (m: ChatMessage) => {
      if (!m.spec) return;
      const snap = snapshot(); // re-baseline so a later Undo is still exact
      applyGraph(m.spec);
      patch(m.id, { snapshot: snap, proposal: "applied" });
      track("assistant_graph_applied", {
        nodes: m.spec.nodes?.length ?? 0,
        edges: m.spec.edges?.length ?? 0,
        reapply: true,
      });
    },
    [snapshot, applyGraph, patch],
  );

  return (
    <div className="flex h-full flex-col" data-testid="assistant-panel">
      <div className="px-3 pt-3 pb-2">
        <span className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
          AI assistant
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-auto p-3">
        {messages.length === 0 ? (
          <div className="rounded-lg border border-border bg-card p-3 text-xs text-muted-foreground">
            Describe the agent you want — e.g. “I would like a RAG chatbot for my website” —
            and I’ll draft it live on the canvas for you to approve.
          </div>
        ) : null}

        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="flex justify-end">
              <div className="max-w-[85%] rounded-lg bg-primary px-3 py-2 text-xs text-primary-foreground">
                {m.content}
              </div>
            </div>
          ) : (
            <div key={m.id} className="flex flex-col gap-1.5" data-testid="assistant-message">
              {m.notice ? (
                <div
                  className="rounded-lg border border-border bg-muted px-3 py-2 text-[11px] text-muted-foreground"
                  data-testid="assistant-notice"
                >
                  ℹ️ {m.notice}
                </div>
              ) : null}
              <div
                className={`max-w-[90%] rounded-lg border px-3 py-2 text-xs ${
                  m.error
                    ? "border-destructive/40 bg-destructive/10 text-destructive"
                    : "border-border bg-card text-foreground"
                }`}
              >
                {m.thinking ? (
                  <span className="assistant-shimmer font-medium" data-testid="assistant-status">
                    Thinking…
                  </span>
                ) : (
                  m.content
                )}
              </div>

              {/* Proposal controls — the graph is already previewed on the canvas. */}
              {m.spec && m.proposal ? (
                <div className="flex flex-col gap-1.5">
                  <span className="px-0.5 text-[11px] text-muted-foreground">
                    {nodeSummary(m.spec)}
                  </span>
                  {m.proposal === "preview" ? (
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        className="h-7 px-2.5 text-xs"
                        data-testid="assistant-apply"
                        onClick={() => onApply(m)}
                      >
                        <Check className="h-3.5 w-3.5" /> Apply
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2.5 text-xs text-muted-foreground"
                        data-testid="assistant-discard"
                        onClick={() => onRevert(m)}
                      >
                        <X className="h-3.5 w-3.5" /> Discard
                      </Button>
                    </div>
                  ) : m.proposal === "applied" ? (
                    <div className="flex items-center gap-2">
                      <span className="flex items-center gap-1 text-[11px] text-emerald-500">
                        <Check className="h-3 w-3" /> Applied
                      </span>
                      <button
                        type="button"
                        data-testid="assistant-restore"
                        onClick={() => onRevert(m)}
                        className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-muted-foreground transition hover:bg-muted hover:text-foreground"
                      >
                        <RotateCcw className="h-3 w-3" /> Undo
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-muted-foreground">Dismissed</span>
                      <button
                        type="button"
                        data-testid="assistant-reapply"
                        onClick={() => onReapply(m)}
                        className="flex items-center gap-1 rounded-md px-2 py-1 text-[11px] text-muted-foreground transition hover:bg-muted hover:text-foreground"
                      >
                        <RotateCcw className="h-3 w-3" /> Re-apply
                      </button>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          ),
        )}
      </div>

      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2">
          <Input
            placeholder="Describe your agent…"
            value={input}
            disabled={busy}
            data-testid="assistant-input"
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send();
              }
            }}
          />
          <Button
            size="sm"
            disabled={busy || !input.trim()}
            onClick={() => void send()}
            data-testid="assistant-send"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : "Send"}
          </Button>
        </div>
      </div>
    </div>
  );
}
