"use client";

import { MeshGradient } from "@paper-design/shaders-react";
import { useCallback, useEffect, useRef, useSyncExternalStore } from "react";

/**
 * The atmospheric backdrop for the auth pages — a slow WebGL mesh gradient in brand cyan over
 * near-black, which leans toward the pointer as you move across the page.
 *
 * Deliberately *not* the share page's `AsciiField`: that ASCII flow-field is the signature of a
 * shared agent and should stay unique to it. Same family of atmosphere, different instrument.
 * Built on `@paper-design/shaders-react`, which was already a dependency of this app.
 *
 * Everything here is decorative. It sits behind the card with `pointer-events-none`, is
 * `aria-hidden`, and a static CSS gradient underlay carries the look on its own if WebGL never
 * comes up — so the page is never a black void on a machine without a GPU (headless CI included).
 */

// How far the field drifts toward the pointer, in pixels at the extremes of the viewport. Small
// on purpose: this is a backdrop, and a large excursion turns it into a toy.
const REACH = 60;
// The shader layer is inflated past the viewport by this much so the parallax never drags an
// empty edge into view.
const OVERSCAN = REACH * 2;
// Per-frame easing toward the target. Low enough that the field trails the cursor rather than
// tracking it, which is what makes it read as a fluid and not a cursor follower.
const EASE = 0.045;

const MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * The visitor's reduced-motion preference, live. Read through `useSyncExternalStore` rather than
 * an effect so the first render already has the right answer and a mid-session change to the OS
 * setting is picked up. The server snapshot is `true` — the still version is the safe default for
 * markup rendered before we can ask.
 */
function useReducedMotion(): boolean {
  const subscribe = useCallback((onChange: () => void) => {
    const motion = window.matchMedia(MOTION_QUERY);
    motion.addEventListener("change", onChange);
    return () => motion.removeEventListener("change", onChange);
  }, []);
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(MOTION_QUERY).matches,
    () => true,
  );
}

/** False during SSR and the first render, true afterwards — WebGL only exists once mounted. */
function useMounted(): boolean {
  return useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
}

export function AuthField() {
  // The parallax is applied as a transform on the shader's wrapper, mutated straight from the rAF
  // loop — never through React state.
  //
  // This is not a micro-optimisation. Feeding the pointer into the shader's own `offsetX`/`offsetY`
  // props re-renders `MeshGradient` on every frame, and the resulting WebGL churn saturates the
  // main thread hard enough to swallow clicks outright: a link on top of this component simply
  // stops navigating. Keeping the shader's props constant means it mounts once and animates
  // itself, and the lean costs a compositor transform.
  const layer = useRef<HTMLDivElement>(null);
  const target = useRef({ x: 0, y: 0 });
  const current = useRef({ x: 0, y: 0 });
  const reduced = useReducedMotion();
  // Server-rendering the shader would emit a canvas the client has to reconcile, for a purely
  // decorative layer — so we wait.
  const mounted = useMounted();

  useEffect(() => {
    // Reduced motion gets a genuinely still frame: no pointer loop at all, not merely a slow one.
    if (reduced) return;

    let raf = 0;
    const onPointer = (clientX: number, clientY: number) => {
      // Pointer position as a signed offset from the centre of the viewport.
      target.current = {
        x: (clientX / window.innerWidth - 0.5) * -2 * REACH,
        y: (clientY / window.innerHeight - 0.5) * -2 * REACH,
      };
    };
    const onMouse = (e: MouseEvent) => onPointer(e.clientX, e.clientY);
    const onTouch = (e: TouchEvent) => {
      const p = e.touches[0];
      if (p) onPointer(p.clientX, p.clientY);
    };
    const onLeave = () => {
      target.current = { x: 0, y: 0 };
    };

    const tick = () => {
      const { x, y } = current.current;
      const next = { x: x + (target.current.x - x) * EASE, y: y + (target.current.y - y) * EASE };
      current.current = next;
      if (layer.current) {
        layer.current.style.transform = `translate3d(${next.x.toFixed(2)}px, ${next.y.toFixed(2)}px, 0)`;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    window.addEventListener("mousemove", onMouse, { passive: true });
    window.addEventListener("touchmove", onTouch, { passive: true });
    window.addEventListener("touchend", onLeave, { passive: true });
    window.addEventListener("mouseleave", onLeave);
    const onVis = () => {
      cancelAnimationFrame(raf);
      if (!document.hidden) raf = requestAnimationFrame(tick);
    };
    document.addEventListener("visibilitychange", onVis);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("touchmove", onTouch);
      window.removeEventListener("touchend", onLeave);
      window.removeEventListener("mouseleave", onLeave);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [reduced]);

  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      {/* The fallback, and the floor the shader composites over. Handsome on its own. */}
      <div
        className="absolute inset-0 bg-[#04060a]"
        style={{
          backgroundImage:
            "radial-gradient(80% 60% at 50% 0%, rgba(34,211,238,0.16), transparent 60%), radial-gradient(60% 50% at 20% 100%, rgba(56,89,238,0.14), transparent 60%)",
        }}
      />
      {mounted ? (
        <div
          ref={layer}
          className="absolute opacity-[0.68] will-change-transform"
          style={{
            inset: `-${OVERSCAN}px`,
          }}
        >
          <MeshGradient
            className="h-full w-full"
            // Near-black ground with a cyan highlight and an indigo counterweight. Paired with the
            // vignette below, this keeps the card the brightest thing on the page.
            colors={["#04060a", "#0b2a33", "#22d3ee", "#1e3a8a"]}
            distortion={0.8}
            swirl={0.5}
            grainOverlay={0.06}
            speed={reduced ? 0 : 0.18}
            // Caps the work on high-DPR displays. The library's own knob, so it stays correct if
            // the sizing model changes underneath us.
            maxPixelCount={1920 * 1080}
            minPixelRatio={1}
          />
        </div>
      ) : null}
      {/* Vignette — pulls the eye to the card and keeps text contrast honest, mirroring the
          share page's stage treatment. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(105% 80% at 50% 45%, rgba(4,6,10,0.12) 0%, rgba(4,6,10,0.72) 55%, rgba(4,6,10,0.94) 100%)",
        }}
      />
    </div>
  );
}
