"use client";

/**
 * The Video tile's player — the only interactive leaf in the Capabilities section, and the only
 * place on the landing page that plays real generated output (`public/capability-video.mp4`,
 * a Seedance render).
 *
 * It starts when the pointer enters the **card**, not this element, so hovering the title or the
 * body copy counts. The card is a server component, so it cannot hand down a callback; instead
 * it marks itself `data-capability-card` and this component binds to its nearest one. That's an
 * explicit contract between the two rather than a guess at DOM shape.
 *
 * The clip is `preload="none"`: 1.5 MB should not be on the critical path for a decorative tile
 * below the fold, so nothing is fetched until someone actually hovers. The poster covers the
 * element until `playing` fires, which is what keeps the first hover from flashing black.
 *
 * Playback progress is written straight to the bar's `style.transform` from `timeupdate` — the
 * section's "no animation loops in React" rule holds, and the bar tracks the real currentTime
 * instead of a keyframe that hopes to stay in sync with it.
 */

import { useCallback, useEffect, useRef, useState } from "react";

/** The clip's own length, for the timecode. Cheap to state; avoids a render on `loadedmetadata`. */
const DURATION_LABEL = "0:05";

export function VideoPreview() {
  const video = useRef<HTMLVideoElement>(null);
  const bar = useRef<HTMLSpanElement>(null);
  const root = useRef<HTMLDivElement>(null);
  const [playing, setPlaying] = useState(false);

  const play = useCallback(() => {
    const el = video.current;
    if (!el) return;
    // A muted, inline video is allowed to start without a user gesture; the promise still
    // rejects if the browser declines (low power mode, data saver), and there is nothing to do
    // about that but leave the poster up.
    void el.play().catch(() => {});
  }, []);

  const stop = useCallback(() => {
    const el = video.current;
    if (!el) return;
    el.pause();
    el.currentTime = 0;
    if (bar.current) bar.current.style.transform = "scaleX(0)";
    setPlaying(false);
  }, []);

  // Bind to the card, so the whole tile is the hover target.
  useEffect(() => {
    const card = root.current?.closest("[data-capability-card]");
    if (!card) return;
    // Auto-play on hover is motion the visitor did not ask for; under reduced motion the tile
    // stays a still and the play button remains the way in.
    const calm = window.matchMedia("(prefers-reduced-motion: reduce)");
    const enter = () => {
      if (!calm.matches) play();
    };
    card.addEventListener("pointerenter", enter);
    card.addEventListener("pointerleave", stop);
    return () => {
      card.removeEventListener("pointerenter", enter);
      card.removeEventListener("pointerleave", stop);
    };
  }, [play, stop]);

  function onTimeUpdate() {
    const el = video.current;
    if (!el || !bar.current || !el.duration) return;
    bar.current.style.transform = `scaleX(${el.currentTime / el.duration})`;
  }

  return (
    <div ref={root}>
      <div className="relative h-40 overflow-hidden bg-black/40">
        <video
          ref={video}
          src="/capability-video.mp4"
          poster="/capability-video-poster.jpg"
          muted
          loop
          playsInline
          preload="none"
          aria-label="A sample clip generated on the canvas"
          onPlaying={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onTimeUpdate={onTimeUpdate}
          className={`h-full w-full object-cover transition-[opacity,filter] duration-500 ${
            playing ? "opacity-100 blur-0" : "opacity-45 blur-[1.5px]"
          }`}
        />

        {/* letterbox bars, so it reads as footage rather than a picture */}
        <span aria-hidden className="absolute inset-x-0 top-0 h-3 bg-black/50" />
        <span aria-hidden className="absolute inset-x-0 bottom-0 h-3 bg-black/50" />

        {/* The button is the touch path — there is no hover on a phone — and the affordance that
            says the still is a clip at all. It fades rather than unmounts so playback isn't
            interrupted by the pointer crossing into where it used to be. */}
        <button
          type="button"
          onClick={() => (playing ? stop() : play())}
          aria-label={playing ? "Stop the sample clip" : "Play the sample clip"}
          className={`absolute inset-0 flex items-center justify-center transition-opacity duration-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand ${
            playing ? "opacity-0" : "opacity-100"
          }`}
        >
          <span className="flex h-11 w-11 items-center justify-center rounded-full bg-white shadow-[0_10px_28px_-6px_rgba(255,255,255,0.55)] transition-transform duration-300 hover:scale-105">
            <svg viewBox="0 0 12 12" aria-hidden className="ml-0.5 h-3.5 w-3.5 fill-black">
              <path d="M3 1.5 10 6 3 10.5Z" />
            </svg>
          </span>
        </button>
      </div>

      {/* render status — the Image tile's prompt row, one step further along the pipeline */}
      <div className="flex items-center gap-2 border-t border-white/10 px-3 py-2">
        <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-white/30">render</span>
        <span className="relative h-1 flex-1 overflow-hidden rounded-full bg-white/10">
          <span
            ref={bar}
            className="absolute inset-y-0 left-0 w-full origin-left rounded-full bg-gradient-to-r from-brand/50 to-brand"
            style={{ transform: "scaleX(0)" }}
          />
        </span>
        <span className="shrink-0 font-mono text-[9px] text-white/45">{DURATION_LABEL}</span>
      </div>
    </div>
  );
}
