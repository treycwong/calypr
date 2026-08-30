"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { downloadUrl, filenameFrom } from "@/lib/download";

// A clip emitted by the Video node (`[▶ Play video.mp4](url)`), rendered as an inline player.
//
// **Inline, unlike `ChatMesh`.** The 3D card is a button that opens a dialog because every mesh in
// a transcript would be its own WebGL context and browsers drop the oldest after about sixteen. A
// `<video>` has no such budget: the browser decodes lazily, and `preload="metadata"` means an
// off-screen clip costs a few kilobytes of headers rather than the whole file. So the thing the
// run produced is simply visible, which is what anyone reading the transcript wanted.
//
// Not autoplayed and not muted-autoplayed: a transcript that starts moving on its own while you
// are reading it is worse than one click.

export function ChatVideo({ src, label }: { src: string; label: string }) {
  const [busy, setBusy] = useState(false);
  const caption = label || "video";

  async function download() {
    if (busy) return;
    setBusy(true);
    try {
      await downloadUrl(src, filenameFrom(caption, "mp4"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="my-1 block max-w-md" data-testid="chat-video">
      <video
        src={src}
        controls
        playsInline
        preload="metadata"
        data-testid="video-open"
        className="w-full rounded-md border border-border"
      />
      <button
        type="button"
        onClick={download}
        disabled={busy}
        data-testid="video-download"
        className="mt-1 inline-flex items-center gap-1 rounded px-1 py-0.5 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-50"
        aria-label="Download video"
      >
        <Download className="h-3.5 w-3.5" />
        {busy ? "Saving…" : ".mp4"}
      </button>
    </span>
  );
}
