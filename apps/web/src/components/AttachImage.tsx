"use client";

import { Paperclip, X } from "lucide-react";
import { useRef, useState } from "react";

// Shared image-attachment UI for the Playground and the share chat: a paperclip button that
// uploads the picked file (client-side 5MB/type pre-check lives in lib/api's upload helpers,
// the API re-enforces server-side) and a removable thumbnail chip for the pending attachment.

export function useAttachment(
  upload: (file: File) => Promise<string>,
  onError: (message: string) => void,
) {
  const [pending, setPending] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function pick(file: File) {
    if (uploading) return;
    setUploading(true);
    try {
      setPending(await upload(file));
    } catch (e) {
      onError(e instanceof Error ? e.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  return { pending, uploading, pick, clear: () => setPending(null) };
}

export function AttachButton({
  onPick,
  uploading,
  disabled,
}: {
  onPick: (file: File) => void;
  uploading: boolean;
  disabled?: boolean;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        className="hidden"
        data-testid="attach-input"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = ""; // allow re-picking the same file
          if (file) onPick(file);
        }}
      />
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        disabled={disabled || uploading}
        data-testid="attach-button"
        aria-label="Attach an image"
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-input text-muted-foreground transition hover:text-foreground disabled:opacity-50"
      >
        <Paperclip className={`h-4 w-4 ${uploading ? "animate-pulse" : ""}`} />
      </button>
    </>
  );
}

export function AttachmentChip({ url, onRemove }: { url: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/40 p-1">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={url} alt="attachment" className="h-10 w-10 rounded object-cover" />
      <button
        type="button"
        onClick={onRemove}
        data-testid="attach-remove"
        aria-label="Remove attachment"
        className="text-muted-foreground transition hover:text-foreground"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </span>
  );
}

/** The thumbnail(s) shown inside a sent user bubble. */
export function SentImages({ urls }: { urls: string[] }) {
  if (!urls.length) return null;
  return (
    <span className="mb-1 flex flex-wrap justify-end gap-1">
      {urls.map((u) => (
        // eslint-disable-next-line @next/next/no-img-element
        <img key={u} src={u} alt="attachment" className="h-20 max-w-full rounded object-cover" />
      ))}
    </span>
  );
}
