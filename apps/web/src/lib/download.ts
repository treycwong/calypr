// Download a media URL (a `data:` URI or a public blob URL) to disk. Fetches it into a blob so the
// `download` attribute is honored even for cross-origin URLs; falls back to opening in a new tab if
// the fetch is blocked. Shared by the image and audio chat embeds.

export async function downloadUrl(src: string, filename: string): Promise<void> {
  try {
    const res = await fetch(src);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch {
    window.open(src, "_blank", "noopener");
  }
}

// Turn a caption into a safe filename slug with the given extension (e.g. "A Dog!" -> "a-dog.png").
export function filenameFrom(caption: string, ext: string): string {
  const base =
    caption
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 40) || "file";
  return `${base}.${ext}`;
}
