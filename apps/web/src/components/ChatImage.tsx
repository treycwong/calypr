"use client";

import { Download } from "lucide-react";
import { useState } from "react";

import { downloadUrl, filenameFrom } from "@/lib/download";

// An image emitted by the Image node (`![alt](url)`), with a download control beneath it. The url
// is either a `data:` URI (no blob store) or a public Vercel Blob URL; `downloadUrl` handles both.

function extFromSrc(src: string): string {
  const m = /^data:image\/([a-z0-9]+)/i.exec(src);
  return m ? m[1].split("+")[0] : "png";
}

export function ChatImage({ src, alt }: { src: string; alt: string }) {
  const [busy, setBusy] = useState(false);

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
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        className="max-w-full rounded-md border border-border"
        loading="lazy"
      />
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
    </span>
  );
}
