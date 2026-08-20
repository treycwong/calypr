"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp } from "lucide-react";

import {
  AttachButton,
  AttachmentChip,
  SentImages,
  useAttachment,
} from "@/components/AttachImage";
import { ScoreStrip } from "@/components/cards/ScoreStrip";
import { hasCards, useStudy } from "@/components/cards/useStudy";
import { Markdown } from "@/components/Markdown";
import { useToast } from "@/components/ui/toast";
import { track } from "@/lib/analytics";
import { runShare, uploadShareImage } from "@/lib/api";

type ChatMsg = { role: "user" | "assistant"; text: string; images?: string[] };

/** Quick follow-ups offered once a drill is running — ordinary sends, so no new run path. */
const INTENTS = ["Next", "Harder", "Explain that"];

// The refined, public-facing chat for a shared agent. Spec-free by design: it streams through
// `runShare(token, …)` and never touches the graph. Styled as a floating glass terminal over
// the ASCII field, and built mobile-first (the composer pins to the bottom with safe-area).
export function ShareChat({ token, agentName }: { token: string; agentName: string }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  // Not minted here. On a public share link the conversation id is the only thing separating
  // two anonymous visitors, so the server mints it (`secrets`, 128 bits) and sends it back as
  // the first event; we hold it and echo it to continue. A browser-chosen `Math.random` value
  // was guessable enough that naming someone else's id resumed their conversation.
  const [threadId, setThreadId] = useState<string | undefined>(undefined);
  const logRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();
  // Scoped to the conversation, not the link: two visitors on the same public token are strangers
  // and must not share a tally. Before the server mints the id there is nothing to grade yet.
  const study = useStudy(`share:${token}:${threadId ?? "new"}`, "glass");
  // A study project announces itself by emitting cards. Nothing here reads the project's config —
  // the GraphSpec never reaches this page by design, and it doesn't need to.
  const studying = useMemo(() => hasCards(messages.map((m) => m.text)), [messages]);
  const attach = useAttachment(
    (file) => uploadShareImage(token, file),
    (msg) => toast(msg, "error"),
  );

  // Keep the newest message in view as tokens stream in.
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  /** `override` lets a study intent button ("Next", "Harder") send without typing. It is an
   *  ordinary turn in every other respect — same stream, same thread, same tally. */
  async function send(override?: string) {
    const text = (override ?? input).trim();
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
    track("run_started", { share: true });
    let errored = false;
    try {
      for await (const ev of runShare(token, text, threadId, images)) {
        if (ev.type === "thread") setThreadId(ev.thread_id);
        else if (ev.type === "token") apply(ev.text);
        else if (ev.type === "error") {
          errored = true;
          apply(`⚠️ ${ev.message}`);
          toast(ev.message, "error");
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

      {studying ? <ScoreStrip score={study.score} variant="glass" /> : null}

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
          messages.map((m, i) => {
            // A turn carrying a card breaks out of the bubble and spans the panel — the single
            // change that stops a drill from reading as a chat with widgets in it.
            const carded = m.role === "assistant" && hasCards([m.text]);
            return (
            <div
              key={i}
              className={
                carded ? "block" : m.role === "user" ? "flex justify-end" : "flex justify-start"
              }
            >
              <div
                data-testid={`msg-${m.role}`}
                className={
                  carded
                    ? "w-full text-sm leading-relaxed text-white/90"
                    : m.role === "user"
                      ? "max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm border border-cyan-400/20 bg-cyan-500/15 px-3.5 py-2 text-sm text-cyan-50"
                      : "max-w-[85%] rounded-2xl rounded-bl-sm border border-white/10 bg-white/[0.04] px-3.5 py-2 text-sm leading-relaxed text-white/90"
                }
              >
                {m.role === "assistant" ? (
                  m.text ? (
                    <Markdown text={m.text} cards={study.cards} />
                  ) : (
                    <span className="inline-block animate-pulse text-cyan-300/80">▋</span>
                  )
                ) : (
                  <>
                    <SentImages urls={m.images ?? []} />
                    {m.text}
                  </>
                )}
              </div>
            </div>
            );
          })
        )}
      </div>

      {/* Composer */}
      <form
        className="border-t border-white/5 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3"
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
        {studying && !busy ? (
          <div className="mb-2 flex flex-wrap gap-1.5" data-testid="study-intents">
            {INTENTS.map((intent) => (
              <button
                key={intent}
                type="button"
                onClick={() => void send(intent)}
                className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/70 transition hover:border-cyan-400/40 hover:text-white"
              >
                {intent}
              </button>
            ))}
          </div>
        ) : null}
        <div className="flex items-center gap-2">
        <AttachButton onPick={attach.pick} uploading={attach.uploading} disabled={busy} />
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
        </div>
      </form>
    </div>
  );
}
