"use client";

import { Box, Download } from "lucide-react";
import { useState } from "react";

import { MediaViewer } from "@/components/MediaViewer";
import { downloadUrl, filenameFrom } from "@/lib/download";

// A 3D model emitted by the 3D node (`[⬇ Download model.glb](url)`), rendered as a compact card
// that opens the full viewer.
//
// **Deliberately not an inline <model-viewer>.** Every mesh in a transcript would be its own WebGL
// context, and browsers cap those at around sixteen before they start dropping the oldest — so a
// long conversation would silently blank its earlier models. One viewer, in the dialog, means at
// most one context is ever live. It also keeps three.js out of the chat entirely: the heavy chunk
// is fetched when someone actually opens a model, not when a message scrolls past.

export function ChatMesh({ src, label }: { src: string; label: string }) {
  const [viewing, setViewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const caption = label || "3D model";

  async function download() {
    if (busy) return;
    setBusy(true);
    try {
      await downloadUrl(src, filenameFrom(caption, "glb"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="my-1 inline-flex max-w-full items-center gap-2 rounded-md border border-border bg-white/[0.02] px-2 py-1.5">
      <Box className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <button
        type="button"
        onClick={() => setViewing(true)}
        data-testid="mesh-open"
        className="text-xs font-medium underline underline-offset-2 hover:no-underline"
      >
        View 3D model
      </button>
      <button
        type="button"
        onClick={download}
        disabled={busy}
        data-testid="mesh-download"
        className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-50"
        aria-label="Download 3D model"
      >
        <Download className="h-3.5 w-3.5" />
        {busy ? "Saving…" : ".glb"}
      </button>
      <MediaViewer
        open={viewing}
        onOpenChange={setViewing}
        kind="3d"
        src={src}
        caption={caption}
      />
    </span>
  );
}
