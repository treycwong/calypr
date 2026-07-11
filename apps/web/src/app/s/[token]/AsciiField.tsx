"use client";

import { useEffect, useRef } from "react";

// An abstract, living ASCII flow-field rendered to a canvas — the atmospheric backdrop for a
// shared agent. Layered sine "plasma" drifts across a monospace grid; the pointer (mouse or
// touch) pushes a soft bright ripple through it. Tuned to stay in the background: low-opacity
// brand cyan, coarse grid on small screens, DPR-capped, paused when hidden, and reduced to a
// near-still frame when the visitor prefers reduced motion.
const RAMP = " .·:-=+*≈#%@";

export function AsciiField() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let cols = 0;
    let rows = 0;
    let cell = 16;
    // Pointer, in grid coordinates. Starts off-canvas so nothing glows until the visitor moves.
    const pointer = { x: -999, y: -999, active: false };
    let raf = 0;
    let t = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      // Coarser grid on phones (fewer glyphs → cheaper + less busy behind the chat).
      cell = width < 640 ? 20 : 15;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.font = `${cell}px "Geist Mono", ui-monospace, monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      cols = Math.ceil(width / cell);
      rows = Math.ceil(height / cell);
    };

    const toGrid = (clientX: number, clientY: number) => {
      pointer.x = clientX / cell;
      pointer.y = clientY / cell;
      pointer.active = true;
    };
    const onMouse = (e: MouseEvent) => toGrid(e.clientX, e.clientY);
    const onTouch = (e: TouchEvent) => {
      const p = e.touches[0];
      if (p) toGrid(p.clientX, p.clientY);
    };
    const onLeave = () => {
      pointer.active = false;
      pointer.x = -999;
      pointer.y = -999;
    };

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      // A slow auto-drifting focus when no pointer is present (touch idle / desktop at rest),
      // so the field always feels alive.
      const driftX = (Math.sin(t * 0.15) * 0.35 + 0.5) * cols;
      const driftY = (Math.cos(t * 0.11) * 0.35 + 0.5) * rows;
      const fx = pointer.active ? pointer.x : driftX;
      const fy = pointer.active ? pointer.y : driftY;

      for (let gy = 0; gy < rows; gy++) {
        for (let gx = 0; gx < cols; gx++) {
          // Layered sines → an organic plasma value in [0,1].
          let v =
            Math.sin(gx * 0.22 + t) +
            Math.cos(gy * 0.26 - t * 0.8) +
            Math.sin((gx + gy) * 0.16 + t * 0.5);
          v = (v + 3) / 6;

          // Soft radial ripple around the focus point — a bright ring that eases with distance.
          const dx = gx - fx;
          const dy = gy - fy;
          const dist = Math.sqrt(dx * dx + dy * dy);
          const ripple = Math.max(0, 1 - dist / 14);
          const glow = ripple * (0.6 + 0.4 * Math.sin(dist * 0.6 - t * 3));

          const intensity = Math.min(1, v * 0.6 + glow);
          if (intensity < 0.06) continue;

          const char = RAMP[Math.min(RAMP.length - 1, Math.floor(intensity * RAMP.length))];
          // Brand cyan; near the pointer it warms toward white for a "hot" ring.
          const a = 0.05 + intensity * 0.5;
          const warm = Math.floor(glow * 180);
          ctx.fillStyle = `rgba(${34 + warm}, ${211}, ${238}, ${a})`;
          ctx.fillText(char, gx * cell + cell / 2, gy * cell + cell / 2);
        }
      }

      t += reduced ? 0.0015 : 0.012;
      raf = requestAnimationFrame(render);
    };

    resize();
    render();
    window.addEventListener("resize", resize);
    window.addEventListener("mousemove", onMouse, { passive: true });
    window.addEventListener("touchmove", onTouch, { passive: true });
    window.addEventListener("touchend", onLeave, { passive: true });
    window.addEventListener("mouseleave", onLeave);
    const onVis = () => {
      if (document.hidden) cancelAnimationFrame(raf);
      else raf = requestAnimationFrame(render);
    };
    document.addEventListener("visibilitychange", onVis);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouse);
      window.removeEventListener("touchmove", onTouch);
      window.removeEventListener("touchend", onLeave);
      window.removeEventListener("mouseleave", onLeave);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
    />
  );
}
