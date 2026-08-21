"use client";

import { Download } from "lucide-react";
import dynamic from "next/dynamic";
import { useState } from "react";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { downloadUrl, filenameFrom } from "@/lib/download";

// The 3D viewer pulls its own copy of three.js (~megabytes), so it must never reach a bundle that
// isn't showing a mesh. `ssr: false` because it is a custom element that touches `window` on
// import, and `dynamic` keeps it in a chunk fetched at mount rather than at page load.
const ModelViewer = dynamic(() => import("@/components/ModelViewer"), {
  ssr: false,
  loading: () => <div className="aspect-square w-full animate-pulse rounded-md bg-white/5" />,
});

export type MediaKind = "image" | "3d";

/**
 * The one full-size viewer, shared by the chat and the Media rail.
 *
 * One component rather than a lightbox per surface: an image opened from a chat bubble and the
 * same image opened from the Media grid should be the same window, and three near-identical
 * dialogs is how they stop being. `kind` is the only branch — everything around it (sizing,
 * dismissal, the download control) is common.
 *
 * Dismissal, focus trapping and the Escape key come from `ui/dialog` (Radix), so this doesn't
 * reimplement any of it. The dialog is the *only* fullscreen surface either viewer gets: the
 * inline ones stay bounded inside their container.
 */
export function MediaViewer({
  open,
  onOpenChange,
  kind,
  src,
  caption,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  kind: MediaKind;
  src: string;
  /** Also the download filename and the accessible name — a viewer with no title is a dead end
   *  for a screen reader, and Radix warns when `DialogTitle` is missing. */
  caption: string;
}) {
  const [busy, setBusy] = useState(false);

  async function download() {
    if (busy) return;
    setBusy(true);
    try {
      await downloadUrl(src, filenameFrom(caption, kind === "3d" ? "glb" : "png"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl" data-testid="media-viewer">
        <DialogTitle className="truncate text-sm font-medium">{caption || "Preview"}</DialogTitle>
        {kind === "image" ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={src}
            alt={caption}
            className="max-h-[70vh] w-full rounded-md object-contain"
            data-testid="media-viewer-image"
          />
        ) : (
          <ModelViewer src={src} alt={caption} className="h-[60vh] w-full" />
        )}
        <button
          type="button"
          onClick={download}
          disabled={busy}
          data-testid="media-viewer-download"
          className="inline-flex items-center gap-1 self-start rounded px-1 py-0.5 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-50"
        >
          <Download className="h-3.5 w-3.5" />
          {busy ? "Saving…" : "Download"}
        </button>
      </DialogContent>
    </Dialog>
  );
}
