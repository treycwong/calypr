"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";

import { Markdown } from "@/components/Markdown";
import { track } from "@/lib/analytics";
import { runShare } from "@/lib/api";

type ChatMsg = { role: "user" | "assistant"; text: string };

// The refined, public-facing chat for a shared agent. Spec-free by design: it streams through
// `runShare(token, …)` and never touches the graph. Styled as a floating glass terminal over
// the ASCII field, and built mobile-first (the composer pins to the bottom with safe-area).
export function ShareChat({ token, agentName }: { token: string; agentName: string }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const newThread = () => `share-${Math.random().toString(36).slice(2)}`;
  const [threadId] = useState(newThread);
  const logRef = useRef<HTMLDivElement>(null);

  // Keep the newest message in view as tokens stream in.
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

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
    track("run_started", { share: true });
    let errored = false;
    try {
      for await (const ev of runShare(token, text, threadId)) {
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

  const empty = messages.length === 0;

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-cyan-400/15 bg-black/40 shadow-[0_0_120px_-30px_rgba(34,211,238,0.45)] backdrop-blur-xl">
      {/* Header */}
      <div className="flex items-center gap-2.5 border-b border-white/5 px-4 py-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-cyan-300 to-cyan-600 text-sm font-bold text-black">
          C
        </span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-white" data-testid="share-agent-name">
            {agentName}
          </p>
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-cyan-300/60">
            shared agent
          </p>
        </div>
      </div>

      {/* Messages */}
      <div ref={logRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-5" data-testid="chat-log">
        {empty ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
            <p className="font-mono text-sm text-cyan-200/80">
              {`> talk to ${agentName}`}
              <span className="ml-0.5 inline-block animate-pulse text-cyan-300">▋</span>
            </p>
            <p className="max-w-xs text-xs text-white/40">
              Send a message to run this agent live. Your conversation stays on this link.
            </p>
          </div>
        ) : (
          messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
              <div
                data-testid={`msg-${m.role}`}
                className={
                  m.role === "user"
                    ? "max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm border border-cyan-400/20 bg-cyan-500/15 px-3.5 py-2 text-sm text-cyan-50"
                    : "max-w-[85%] rounded-2xl rounded-bl-sm border border-white/10 bg-white/[0.04] px-3.5 py-2 text-sm leading-relaxed text-white/90"
                }
              >
                {m.role === "assistant" ? (
                  m.text ? (
                    <Markdown text={m.text} />
                  ) : (
                    <span className="inline-block animate-pulse text-cyan-300/80">▋</span>
                  )
                ) : (
                  m.text
                )}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Composer */}
      <form
        className="flex items-center gap-2 border-t border-white/5 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Message this agent…"
          data-testid="chat-input"
          disabled={busy}
          className="h-11 min-w-0 flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-4 text-sm text-white placeholder:text-white/30 outline-none transition focus:border-cyan-400/40 focus:bg-white/[0.05] disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          data-testid="chat-send"
          aria-label="Send message"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-300 to-cyan-600 text-black transition hover:brightness-110 disabled:opacity-30 disabled:hover:brightness-100"
        >
          <ArrowUp className="h-5 w-5" strokeWidth={2.5} />
        </button>
      </form>
    </div>
  );
}
