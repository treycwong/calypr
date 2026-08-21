"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { MediaViewer } from "@/components/MediaViewer";
import { downloadUrl, filenameFrom } from "@/lib/download";

// An image emitted by the Image node (`![alt](url)`), with a download control beneath it. The url
// is either a `data:` URI (no blob store) or a public Vercel Blob URL; `downloadUrl` handles both.

function extFromSrc(src: string): string {
  const m = /^data:image\/([a-z0-9]+)/i.exec(src);
  return m ? m[1].split("+")[0] : "png";
}

export function ChatImage({ src, alt }: { src: string; alt: string }) {
  const [busy, setBusy] = useState(false);
  const [viewing, setViewing] = useState(false);

  async function download() {
    if (busy) return;
    setBusy(true);
    try {
      await downloadUrl(src, filenameFrom(alt, extFromSrc(src)));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="my-1 inline-flex max-w-full flex-col items-start gap-1">
      {/* A button, not an <img> with onClick: opening a dialog is an action, and this way it is
          keyboard-reachable and announced without hand-rolling the role and key handling. */}
      <button
        type="button"
        onClick={() => setViewing(true)}
        data-testid="image-open"
        aria-label={`View ${alt || "image"} full size`}
        className="cursor-zoom-in rounded-md transition hover:opacity-90"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={alt}
          className="max-w-full rounded-md border border-border"
          loading="lazy"
        />
      </button>
      <button
        type="button"
        onClick={download}
        disabled={busy}
        data-testid="image-download"
        className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-50"
        aria-label="Download image"
      >
        <Download className="h-3.5 w-3.5" />
        {busy ? "Saving…" : "Download"}
      </button>
      <MediaViewer
        open={viewing}
        onOpenChange={setViewing}
        kind="image"
        src={src}
        caption={alt}
      />
    </span>
  );
}
