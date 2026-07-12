"use client";

import { useState } from "react";

import type { GraphSpec } from "@calypr/dsl";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Markdown } from "@/components/Markdown";
import { track } from "@/lib/analytics";
import { runAgent } from "@/lib/api";

type ChatMsg = { role: "user" | "assistant"; text: string };

export function Playground({ getGraph }: { getGraph: () => GraphSpec }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const newThread = () => `web-${Math.random().toString(36).slice(2)}`;
  const [threadId, setThreadId] = useState(newThread);

  // Start a fresh conversation thread — clears history (and recovers a thread that a tool
  // error may have left mid-tool-call).
  function reset() {
    if (busy) return;
    setMessages([]);
    setThreadId(newThread());
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text }, { role: "assistant", text: "" }]);
    const apply = (chunk: string) =>
      setMessages((m) => {
        const copy = [...m];
        const last = copy[copy.length - 1];
        copy[copy.length - 1] = { role: "assistant", text: last.text + chunk };
        return copy;
      });
    const graph = getGraph();
    track("run_started", { nodes: graph.nodes?.length ?? 0 });
    let errored = false;
    try {
      for await (const ev of runAgent(graph, text, threadId)) {
        if (ev.type === "token") apply(ev.text);
        else if (ev.type === "error") {
          errored = true;
          apply(`⚠️ ${ev.message}`);
        }
      }
      track(errored ? "run_errored" : "run_completed");
    } catch {
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
                m.text
              )}
            </div>
          </div>
        ))}
      </div>
      <form
        className="flex gap-2 border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
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
      </form>
    </div>
  );
}
