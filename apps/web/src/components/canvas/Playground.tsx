"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { GraphSpec } from "@calypr/dsl";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { track } from "@/lib/analytics";
import { isKeyProblem } from "@/lib/errors";
import { type ConversationDetail, runAgent } from "@/lib/api";
import { type CalyprNodeType, NODE_LABELS } from "@/lib/graph";

import { HistoryTab } from "./playground/HistoryTab";
import { PlaygroundChat, type ChatMsg } from "./playground/PlaygroundChat";

/** A conversation the user reopened, so the composer can warn when the agent has forgotten it. */
type Loaded = { id: string; hasState: boolean };

const newThread = () => `web-${Math.random().toString(36).slice(2)}`;

let seq = 0;
/** Stable per-message keys. The transcript used to be keyed by array index and patched by
 *  mutating `messages[length - 1]`, which is fine until a tab switch or a reload reorders
 *  anything. */
const nextId = () => `m${++seq}`;

/** Blocks whose start isn't worth announcing: Input and Output take no visible time. */
const QUIET_BLOCKS = new Set(["input", "output"]);
/** Blocks that produce a file. They are the slow ones, and "generating" says what's happening. */
const MEDIA_BLOCKS = new Set(["image", "mesh", "video", "tts"]);

export function Playground({
  getGraph,
  agentId,
  locked = false,
  scopeReady = true,
  onAssetGenerated,
  onNodeEvent,
  onRunReset,
  onRunFinished,
}: {
  getGraph: () => GraphSpec;
  /** The saved project, when the canvas has been saved. Recorded against the run and the
   *  conversation, and what scopes History to this project. */
  agentId?: string;
  /** The saved project is read-only after a downgrade, so no run may start in it. Passed down
   *  rather than derived here: the API decides it (`locking.py`) and the canvas is what asked. */
  locked?: boolean;
  /** False while the canvas is still resolving `?agent=` from the URL — History waits rather
   *  than briefly listing the wrong scope. */
  scopeReady?: boolean;
  /** A run stored a generated file. Media lives in the left rail (it is workspace-scoped, not
   *  conversation-scoped), so the panel that lists it is not ours to refresh — we just say it
   *  happened. */
  onAssetGenerated?: (asset: Record<string, unknown>) => void;
  // Drives the canvas run animation. `onRunReset` clears prior run state at the start of a
  // send (and on New chat); `onNodeEvent` reports node enter/exit and run errors.
  onNodeEvent?: (nodeId: string, phase: "start" | "end") => void;
  onRunReset?: (opts?: { error?: boolean }) => void;
  // Fires once a send has settled, however it ended. The credit balance in the canvas header is
  // read at page load, and a run is the thing that moves it — without this the number a user
  // watches while deciding whether to run again is the one from before their last few runs.
  onRunFinished?: () => void;
}) {
  // **All of this lives here, not in the Chat tab.** base-ui unmounts an inactive `TabsContent`,
  // so state owned by the chat panel would be destroyed the moment someone clicked History
  // mid-answer — taking the in-flight stream's target with it.
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [busy, setBusy] = useState(false);
  // The blocks running right now, as the chat should name them ("Video · generating…").
  //
  // A Video block runs for one to three minutes with nothing streaming into the transcript, and
  // the canvas glow alone was not enough: with the Playground open the running block can sit
  // off the edge of the narrowed canvas. This line says what is happening whatever the canvas
  // is showing. Keyed by node id, so a fan-out lists each branch until its own `end`.
  const [running, setRunning] = useState<Record<string, string>>({});
  const [threadId, setThreadId] = useState(newThread);
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [tab, setTab] = useState("chat");
  const { toast } = useToast();

  // Aborts the in-flight run. Without this, closing the Playground leaves the request running
  // until the abandoned async generator is finalized — non-deterministic, and the server ends up
  // recording the half-written answer as an error instead of as a partial.
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  /** Stop the run in flight. The abort surfaces as `AbortError` in `send`, and the server's
   *  disconnect arm keeps whatever streamed as a `partial` turn — so the text on screen is the
   *  text that was saved. */
  const stop = useCallback(() => {
    abort.current?.abort();
  }, []);

  const reset = useCallback(() => {
    if (busy) return;
    abort.current?.abort();
    setMessages([]);
    setThreadId(newThread());
    setLoaded(null);
    onRunReset?.();
  }, [busy, onRunReset]);

  /** Reopen a conversation from History: its transcript comes from the database, never from the
   *  checkpoint. Replaying it into the agent's state would re-cost tokens and silently make
   *  reopening an old chat expensive, so we don't. */
  const openConversation = useCallback(
    (detail: ConversationDetail) => {
      abort.current?.abort();
      setMessages(
        detail.messages.map((m) => ({
          id: nextId(),
          role: m.role,
          text: m.text,
          images: m.images,
          status: m.status,
        })),
      );
      setThreadId(detail.thread_id);
      setLoaded({ id: detail.id, hasState: detail.has_state });
      setTab("chat");
      onRunReset?.();
    },
    [onRunReset],
  );

  /** Called by History when the conversation currently on screen is deleted. */
  const forgetIfOpen = useCallback(
    (conversationId: string) => {
      if (loaded?.id === conversationId) reset();
    },
    [loaded, reset],
  );

  async function send(text: string, images: string[]) {
    if (!text || busy) return;
    const assistantId = nextId();
    setBusy(true);
    setMessages((m) => [
      ...m,
      { id: nextId(), role: "user", text, images },
      { id: assistantId, role: "assistant", text: "" },
    ]);
    const patch = (fn: (prev: ChatMsg) => ChatMsg) =>
      setMessages((m) => m.map((msg) => (msg.id === assistantId ? fn(msg) : msg)));
    const append = (chunk: string) => patch((prev) => ({ ...prev, text: prev.text + chunk }));

    const graph = getGraph();
    const typeOf = new Map((graph.nodes ?? []).map((n) => [n.id, n.type as string]));
    const onNode = (nodeId: string, phase: "start" | "end") => {
      const type = typeOf.get(nodeId) ?? "";
      if (QUIET_BLOCKS.has(type)) return;
      setRunning((prev) => {
        const next = { ...prev };
        if (phase === "end") delete next[nodeId];
        else {
          const label = NODE_LABELS[type as CalyprNodeType] ?? "Block";
          next[nodeId] = `${label} · ${MEDIA_BLOCKS.has(type) ? "generating" : "running"}…`;
        }
        return next;
      });
    };
    setRunning({});
    track("run_started", { nodes: graph.nodes?.length ?? 0 });
    onRunReset?.(); // clear the previous run's node glow before this one starts
    const controller = new AbortController();
    abort.current = controller;
    let errored = false;
    try {
      for await (const ev of runAgent(
        graph,
        text,
        threadId,
        images,
        agentId,
        controller.signal,
      )) {
        if (ev.type === "token") append(ev.text);
        else if (ev.type === "node") {
          onNode(ev.node_id, ev.phase);
          onNodeEvent?.(ev.node_id, ev.phase);
        }
        else if (ev.type === "asset") onAssetGenerated?.(ev);
        else if (ev.type === "conversation") {
          // The turn is now durable. A conversation the user just spoke into has live state by
          // definition, so clear any "memory expired" warning they were shown.
          setLoaded({ id: ev.conversation_id, hasState: true });
        } else if (ev.type === "notice") {
          append(`ℹ️ ${ev.message}\n\n`);
          toast(ev.message, "default");
        } else if (ev.type === "error") {
          errored = true;
          onRunReset?.({ error: true });
          append(`⚠️ ${ev.message}`);
          toast(ev.message, "error");
          if (isKeyProblem(ev.code)) {
            patch((prev) => ({ ...prev, keyRejected: true }));
          }
        }
      }
      track(errored ? "run_errored" : "run_completed");
    } catch (err) {
      // An abort is the user pressing Stop (or closing the panel), not a failure.
      if ((err as Error)?.name === "AbortError") {
        // Label it the way History will, so the turn doesn't silently change description when
        // the user reopens it later.
        patch((prev) => ({ ...prev, status: "partial" }));
        track("run_stopped");
      } else {
        onRunReset?.({ error: true });
        track("run_errored");
      }
    } finally {
      if (abort.current === controller) abort.current = null;
      setBusy(false);
      setRunning({});
      onRunFinished?.();
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Fixed height, not padding-driven: "New chat" only exists on the Chat tab, and letting
          the row size to its contents made the header — and everything under it — jump 8px on
          every tab switch. h-11 is the taller state (a `sm` button is h-7 plus px-3/py-2), so
          nothing is clipped and the Media panel's header lines up with this one. */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b border-border px-3">
        <span className="text-sm font-medium">Playground</span>
        {tab === "chat" ? (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={reset}
            disabled={busy}
            data-testid="chat-reset"
          >
            New chat
          </Button>
        ) : null}
      </div>
      <Tabs
        value={tab}
        onValueChange={(v) => setTab(v as string)}
        className="min-h-0 flex-1 gap-0"
      >
        <TabsList
          variant="line"
          className="h-12! w-full justify-start border-b border-border px-2"
          data-testid="playground-tabs"
        >
          <TabsTrigger value="chat" data-testid="tab-chat">
            Chat
          </TabsTrigger>
          <TabsTrigger value="history" data-testid="tab-history">
            History
          </TabsTrigger>
        </TabsList>
        {/* `keepMounted` so the transcript's scroll position survives a trip to History. The
            hoisted state above is what keeps the *run* alive; this is just the DOM. */}
        <TabsContent value="chat" keepMounted className="min-h-0 data-[hidden]:hidden">
          <PlaygroundChat
            messages={messages}
            busy={busy}
            running={Object.values(running)}
            locked={locked}
            scope={threadId}
            memoryExpired={loaded !== null && !loaded.hasState}
            onSend={send}
            onStop={stop}
          />
        </TabsContent>
        <TabsContent value="history" className="min-h-0">
          <HistoryTab
            agentId={agentId}
            scopeReady={scopeReady}
            activeId={loaded?.id ?? null}
            onOpen={openConversation}
            onDeleted={forgetIfOpen}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
