"use client";

import { useState } from "react";

import type { GraphSpec } from "@calypr/dsl";

import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AttachButton,
  AttachmentChip,
  SentImages,
  useAttachment,
} from "@/components/AttachImage";
import { Markdown } from "@/components/Markdown";
import { useToast } from "@/components/ui/toast";
import { track } from "@/lib/analytics";
import { API_KEYS_HREF, PROVIDER_KEY_REJECTED } from "@/lib/errors";
import { runAgent, uploadImage } from "@/lib/api";

type ChatMsg = {
  role: "user" | "assistant";
  text: string;
  images?: string[];
  // A provider rejected the workspace's stored key — render the Fix it affordance.
  keyRejected?: boolean;
};

export function Playground({
  getGraph,
  onNodeEvent,
  onRunReset,
}: {
  getGraph: () => GraphSpec;
  // Drives the canvas run animation. `onRunReset` clears prior run state at the start of a
  // send (and on New chat); `onNodeEvent` reports node enter/exit and run errors.
  onNodeEvent?: (nodeId: string, phase: "start" | "end") => void;
  onRunReset?: (opts?: { error?: boolean }) => void;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const newThread = () => `web-${Math.random().toString(36).slice(2)}`;
  const [threadId, setThreadId] = useState(newThread);
  const { toast } = useToast();
  const attach = useAttachment(uploadImage, (msg) => toast(msg, "error"));

  // Start a fresh conversation thread — clears history (and recovers a thread that a tool
  // error may have left mid-tool-call).
  function reset() {
    if (busy) return;
    setMessages([]);
    setThreadId(newThread());
    attach.clear();
    onRunReset?.();
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    const images = attach.pending ? [attach.pending] : [];
    attach.clear();
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text, images }, { role: "assistant", text: "" }]);
    const apply = (chunk: string) =>
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        copy[copy.length - 1] = { role: "assistant", text: last.text + chunk };
        return copy;
      });
    const graph = getGraph();
    track("run_started", { nodes: graph.nodes?.length ?? 0 });
    onRunReset?.(); // clear the previous run's node glow before this one starts
    let errored = false;
    try {
      for await (const ev of runAgent(graph, text, threadId, images)) {
        if (ev.type === "token") apply(ev.text);
        else if (ev.type === "node") onNodeEvent?.(ev.node_id, ev.phase);
        else if (ev.type === "notice") {
          apply(`\u2139\uFE0F ${ev.message}\n\n`);
          toast(ev.message, "default");
        } else if (ev.type === "error") {
          errored = true;
          onRunReset?.({ error: true });
          apply(`⚠️ ${ev.message}`);
          toast(ev.message, "error");
          if (ev.code === PROVIDER_KEY_REJECTED) {
            setMessages((m) => {
              const copy = [...m];
              copy[copy.length - 1] = { ...copy[copy.length - 1], keyRejected: true };
              return copy;
            });
          }
        }
      }
      track(errored ? "run_errored" : "run_completed");
    } catch {
      onRunReset?.({ error: true });
      track("run_errored");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="text-sm font-medium">Playground</span>
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
      </div>
      <div className="flex-1 space-y-3 overflow-auto p-3" data-testid="chat-log">
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">Send a message to test your agent.</p>
        ) : null}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              data-testid={`msg-${m.role}`}
              className={`inline-block max-w-[90%] rounded-lg px-3 py-2 text-left text-sm ${
                m.role === "user"
                  ? "whitespace-pre-wrap bg-primary text-primary-foreground"
                  : "bg-muted leading-relaxed"
              }`}
            >
              {m.role === "assistant" ? (
                m.text ? (
                  <Markdown text={m.text} />
                ) : busy ? (
                  "…"
                ) : (
                  ""
                )
              ) : (
                <>
                  <SentImages urls={m.images ?? []} />
                  {m.text}
                </>
              )}
            </div>
            {m.keyRejected ? (
              <div className="mt-1.5" data-testid="fix-keys">
                <a
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                  href={API_KEYS_HREF}
                >
                  Fix it — check your API keys
                </a>
              </div>
            ) : null}
          </div>
        ))}
      </div>
      <form
        className="border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        {attach.pending ? (
          <div className="mb-2">
            <AttachmentChip url={attach.pending} onRemove={attach.clear} />
          </div>
        ) : null}
        <div className="flex gap-2">
          <AttachButton onPick={attach.pick} uploading={attach.uploading} disabled={busy} />
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Message your agent…"
            data-testid="chat-input"
            disabled={busy}
          />
          <Button type="submit" disabled={busy} data-testid="chat-send">
            Send
          </Button>
        </div>
      </form>
    </div>
  );
}
