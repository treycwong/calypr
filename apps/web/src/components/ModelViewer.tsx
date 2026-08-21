"use client";

import { useEffect, useRef, useState } from "react";

/**
 * A GLB rendered with Google's `<model-viewer>` custom element.
 *
 * **Only ever reached through `next/dynamic`** (see `MediaViewer`). The import below pulls
 * model-viewer's own bundled three.js, so a static import here would put megabytes of WebGL into
 * every bundle that renders a chat message. Isolating it in this file is what makes the dynamic
 * boundary a single, obvious line rather than something to remember.
 *
 * Constraints this file exists to hold, after a WebGL backdrop once swallowed clicks across
 * thirteen unrelated E2E specs:
 *
 * * The canvas is a **bounded block** sized by its container. Never `fixed`, never `absolute`,
 *   never full-viewport. The modal in `MediaViewer` is the only fullscreen surface, and it is a
 *   real modal that traps its own focus.
 * * Props are **static** — `src` and `alt` are strings. No per-frame prop churn; that, not WebGL
 *   itself, was the mechanism of the earlier failure.
 * * WebGL can be unavailable (blocked, software-rendering disabled, a headless browser). The
 *   element then renders nothing, so `poster` and the caller's own download link are the fallback
 *   rather than an empty box.
 *
 * **`src` is set as an attribute, by hand.** React sets unknown values on a custom element as a
 * *property* (`el.src = …`), and model-viewer only loads from the `src` **attribute** — so writing
 * `<model-viewer src={…}>` in JSX produces an element that reports `loaded: true` with nothing in
 * it. It fails silently and looks exactly like a model that hasn't downloaded yet, which is why
 * this is an effect and a ref rather than a prop.
 */
export default function ModelViewer({
  src,
  alt,
  poster,
  className = "",
}: {
  src: string;
  alt: string;
  /** Shown while the mesh loads and if WebGL never comes up. The source image, usually. */
  poster?: string;
  className?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // Registers the `<model-viewer>` custom element as a side effect. Guarded because a failed
    // chunk fetch (offline, blocked CDN-less deploy) must degrade, not throw during render.
    import("@google/model-viewer")
      .then(() => !cancelled && setReady(true))
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.setAttribute("src", src);
    // Eager, and as an attribute for the same reason as `src`. model-viewer defaults to
    // `loading="lazy"`, which waits on an IntersectionObserver that never fires inside a portalled
    // dialog: the element then sits there with a correct `src`, `loaded: false`, and no network
    // request at all. Eager is also simply right — the user opened the viewer on purpose.
    el.setAttribute("loading", "eager");
    if (poster) el.setAttribute("poster", poster);
    else el.removeAttribute("poster");
  }, [ready, src, poster]);

  if (failed) {
    return (
      <div
        className={`flex items-center justify-center rounded-md border border-border bg-muted/40 text-xs text-muted-foreground ${className}`}
        data-testid="model-viewer-failed"
      >
        3D preview unavailable — use the download link.
      </div>
    );
  }

  if (!ready) {
    return <div className={`animate-pulse rounded-md bg-white/5 ${className}`} aria-hidden="true" />;
  }

  return (
    // @ts-expect-error — `<model-viewer>` is a custom element, not in JSX.IntrinsicElements.
    <model-viewer
      ref={ref}
      alt={alt}
      camera-controls=""
      touch-action="pan-y"
      shadow-intensity="1"
      // `class`, not `className`: React passes unknown attributes through verbatim on a custom
      // element, and the element's own styling reads `class`.
      class={`rounded-md border border-border bg-muted/20 ${className}`}
      data-testid="model-viewer"
    />
  );
}
