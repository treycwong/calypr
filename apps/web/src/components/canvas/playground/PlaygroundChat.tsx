"use client";

import { useEffect, useRef, useState } from "react";

import {
  AttachButton,
  AttachmentChip,
  SentImages,
  useAttachment,
} from "@/components/AttachImage";
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

/** The transcript and composer. Deliberately stateless about the *run*: everything a send needs
 *  lives in `Playground`, because base-ui unmounts this panel when another tab is selected. */
export function PlaygroundChat({
  messages,
  busy,
  memoryExpired,
  onSend,
}: {
  messages: ChatMsg[];
  busy: boolean;
  /** The transcript was reopened but its checkpoint has aged out — the agent has no memory of
   *  what is on screen. Surfaced rather than hidden: the alternative is the user asking a
   *  follow-up and getting a baffling answer. */
  memoryExpired: boolean;
  onSend: (text: string, images: string[]) => void;
}) {
  const [input, setInput] = useState("");
  const { toast } = useToast();
  const attach = useAttachment(uploadImage, (msg) => toast(msg, "error"));
  const logRef = useRef<HTMLDivElement>(null);

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
      <div ref={logRef} className="flex-1 space-y-3 overflow-auto p-3" data-testid="chat-log">
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">Send a message to test your agent.</p>
        ) : null}
        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "text-right" : "text-left"}>
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
        ))}
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
          submit();
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
