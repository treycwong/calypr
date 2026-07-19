"use client";

import { useEffect, useRef } from "react";

// A handful of faint cyan sparks that drift in slow arcs around the hero globe, each leaving a
// short fading trail — the "small trails" around the dithered sphere. Deliberately sparse and dim
// so it reads as atmosphere, not motion. DPR-capped, paused off-screen, frozen under
// prefers-reduced-motion. The parent's radial mask fades it out behind the headline.

type Spark = {
  angle: number; // orbital angle around the globe centre
  radius: number; // 0..1 of the min viewport dimension
  spin: number; // angular velocity (signed)
  drift: number; // slow radial breathing
  size: number;
  trail: Array<{ x: number; y: number }>;
};

const CENTER = { x: 0.5, y: 0.42 }; // matches the hero mask focus
const TRAIL_LEN = 12;

export function HeroTrails() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let width = 0;
    let height = 0;
    let sparks: Spark[] = [];
    let raf = 0;
    let visible = true;
    let lastTime = performance.now();

    const COUNT = () => (width < 640 ? 8 : 16);

    const seed = () => {
      sparks = Array.from({ length: COUNT() }, () => {
        const angle = Math.random() * Math.PI * 2;
        const radius = 0.28 + Math.random() * 0.42;
        return {
          angle,
          radius,
          spin: (Math.random() < 0.5 ? -1 : 1) * (0.03 + Math.random() * 0.05),
          drift: 0.4 + Math.random() * 0.9,
          size: 1 + Math.random() * 1.6,
          trail: [],
        };
      });
    };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = parent.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (sparks.length === 0) seed();
    };

    const posOf = (s: Spark, t: number) => {
      const min = Math.min(width, height);
      // Gentle radial breathing so the ring isn't perfectly rigid.
      const r = (s.radius + Math.sin(t * s.drift + s.angle) * 0.02) * min;
      return {
        x: CENTER.x * width + Math.cos(s.angle) * r,
        y: CENTER.y * height + Math.sin(s.angle) * r * 0.9, // slightly elliptical
      };
    };

    let t = 0;

    const render = (now: number = performance.now()) => {
      const dtMs = Math.min(Math.max(now - lastTime, 0), 50);
      lastTime = now;
      const dt = dtMs / 16.6667;
      t += (reduced ? 0 : 0.01) * dt;

      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = "lighter";

      for (const s of sparks) {
        if (!reduced) s.angle += s.spin * 0.01 * dt;
        const p = posOf(s, t);
        s.trail.push(p);
        if (s.trail.length > TRAIL_LEN) s.trail.shift();

        // Fading tail.
        for (let i = 0; i < s.trail.length - 1; i++) {
          const a = s.trail[i];
          const b = s.trail[i + 1];
          const f = i / TRAIL_LEN; // 0 (oldest) → ~1 (newest)
          ctx.strokeStyle = `rgba(34, 211, 238, ${f * 0.28})`;
          ctx.lineWidth = s.size * f;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        // Bright head.
        ctx.fillStyle = "rgba(120, 230, 245, 0.7)";
        ctx.beginPath();
        ctx.arc(p.x, p.y, s.size * 0.7, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(render);
    };

    resize();
    render();

    const ro = new ResizeObserver(resize);
    ro.observe(parent);
    const io = new IntersectionObserver(
      ([entry]) => {
        const nowVisible = entry.isIntersecting;
        if (nowVisible && !visible) raf = requestAnimationFrame(render);
        if (!nowVisible) cancelAnimationFrame(raf);
        visible = nowVisible;
      },
      { threshold: 0 },
    );
    io.observe(canvas);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
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
