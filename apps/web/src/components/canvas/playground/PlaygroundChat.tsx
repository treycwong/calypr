"use client";

import { Square } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import {
  AttachButton,
  AttachmentChip,
  SentImages,
  useAttachment,
} from "@/components/AttachImage";
import { ScoreStrip } from "@/components/cards/ScoreStrip";
import { hasCards, useStudy } from "@/components/cards/useStudy";
import { Markdown } from "@/components/Markdown";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { uploadImage } from "@/lib/api";
import { API_KEYS_HREF } from "@/lib/errors";

export type ChatMsg = {
  /** Stable key. Index keys broke as soon as a transcript could be reloaded from History. */
  id: string;
  role: "user" | "assistant";
  text: string;
  images?: string[];
  /** `partial` when a run was stopped mid-answer, `errored` when it failed. Only set on turns
   *  loaded back from the database — a live turn's outcome is visible as it happens. */
  status?: "complete" | "partial" | "errored";
  // A provider rejected the workspace's stored key — render the Fix it affordance.
  keyRejected?: boolean;
};

/** Quick follow-ups offered once a drill is running. They are ordinary sends — the agent decides
 *  what "harder" means — which is why study mode needs no new run path. */
const INTENTS = ["Next", "Harder", "Explain that"];

/** The transcript and composer. Deliberately stateless about the *run*: everything a send needs
 *  lives in `Playground`, because base-ui unmounts this panel when another tab is selected. */
export function PlaygroundChat({
  messages,
  busy,
  scope,
  memoryExpired,
  onSend,
  onStop,
}: {
  messages: ChatMsg[];
  busy: boolean;
  /** Identifies the conversation, so each thread keeps its own tally. */
  scope: string;
  /** The transcript was reopened but its checkpoint has aged out — the agent has no memory of
   *  what is on screen. Surfaced rather than hidden: the alternative is the user asking a
   *  follow-up and getting a baffling answer. */
  memoryExpired: boolean;
  onSend: (text: string, images: string[]) => void;
  /** Abort the run in flight. The server keeps whatever streamed, marked `partial`. */
  onStop: () => void;
}) {
  const [input, setInput] = useState("");
  const { toast } = useToast();
  const attach = useAttachment(uploadImage, (msg) => toast(msg, "error"));
  const logRef = useRef<HTMLDivElement>(null);
  const study = useStudy(scope, "panel");
  // Study chrome is driven by what the agent has actually emitted, so the creator sees the real
  // learner experience here before publishing — no preview toggle to get out of sync.
  const studying = useMemo(() => hasCards(messages.map((m) => m.text)), [messages]);

  // Follow the stream. rAF so the scroll runs after the browser has laid the new text out.
  useEffect(() => {
    const el = logRef.current;
    if (!el) return;
    const id = requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
    return () => cancelAnimationFrame(id);
  }, [messages]);

  function submit() {
    const text = input.trim();
    if (!text || busy) return;
    const images = attach.pending ? [attach.pending] : [];
    attach.clear();
    setInput("");
    onSend(text, images);
  }

  return (
    <div className="flex h-full flex-col">
      {studying ? <ScoreStrip score={study.score} variant="panel" /> : null}
      <div ref={logRef} className="flex-1 space-y-3 overflow-auto p-3" data-testid="chat-log">
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">Send a message to test your agent.</p>
        ) : null}
        {messages.map((m) => {
          // A turn carrying a card breaks out of the bubble and spans the panel. That single
          // change is most of what stops a drill from reading as a chat with widgets in it.
          const carded = m.role === "assistant" && hasCards([m.text]);
          return (
          <div key={m.id} className={m.role === "user" ? "text-right" : "text-left"}>
            <div
              data-testid={`msg-${m.role}`}
              className={
                carded
                  ? "block w-full text-left text-sm"
                  : `inline-block max-w-[90%] rounded-lg px-3 py-2 text-left text-sm ${
                      m.role === "user"
                        ? "whitespace-pre-wrap bg-primary text-primary-foreground"
                        : "bg-muted leading-relaxed"
                    }`
              }
            >
              {m.role === "assistant" ? (
                m.text ? (
                  <Markdown text={m.text} cards={study.cards} />
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
            {m.status === "partial" ? (
              <p className="mt-1 text-xs text-muted-foreground" data-testid="msg-partial">
                Stopped before finishing.
              </p>
            ) : null}
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
          );
        })}
      </div>
      {memoryExpired ? (
        <p
          className="border-t border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground"
          data-testid="memory-expired-notice"
        >
          Earlier messages are shown for reference — the agent&rsquo;s memory of this
          conversation has expired.
        </p>
      ) : null}
      <form
        className="border-t border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          // While a run is streaming the same control stops it, so Enter does too — a user who
          // hits Enter again mid-answer means "stop", not "send an empty message".
          if (busy) onStop();
          else submit();
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
              <Button
                key={intent}
                type="button"
                size="sm"
                variant="outline"
                onClick={() => onSend(intent, [])}
              >
                {intent}
              </Button>
            ))}
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
          {/* One control, two jobs. Never disabled while busy — a spinning, dead Send button is
              exactly when a user most wants a way out. `variant` shifts so it doesn't read as
              the same action, and the testid stays `chat-send` so existing specs keep working. */}
          <Button
            type="submit"
            variant={busy ? "outline" : "default"}
            data-testid="chat-send"
            aria-label={busy ? "Stop generating" : "Send message"}
          >
            {busy ? (
              <>
                <Square className="h-3 w-3 fill-current" />
                Stop
              </>
            ) : (
              "Send"
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
