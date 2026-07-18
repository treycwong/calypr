"use client";

import { useEffect, useRef } from "react";

// A living "agent graph" rendered in ASCII — the hero backdrop. Nodes drift through a bounded
// field and connect to nearby neighbors with faint character-drawn edges; every so often a bright
// signal pulse travels along an edge (message-passing between agents). Cool-gray mesh, cyan
// signals. Rasterized into a coarse monospace grid so it reads as ASCII, not a particle demo.
//
// Tuned to sit *behind* the headline: low contrast, masked to fade out where the text lives (the
// parent applies the mask), DPR-capped, coarser + calmer on phones, paused when off-screen, and
// nearly still under prefers-reduced-motion.

type Node = { x: number; y: number; vx: number; vy: number; z: number };
type Pulse = { a: number; b: number; t: number; speed: number };

const MESH = " ·:-=+";

export function HeroAscii() {
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
    let cols = 0;
    let rows = 0;
    let cell = 16;
    let intensity = new Float32Array(0);
    let nodes: Node[] = [];
    let pulses: Pulse[] = [];
    const pointer = { x: 0.5, y: 0.5 };
    let raf = 0;
    let visible = true;
    let t = 0;

    // Connection radius (in domain units, 0..1) and how many nodes/pulses to run.
    const NODE_COUNT = () => (width < 640 ? 34 : 80);
    const LINK_DIST = () => (width < 640 ? 0.24 : 0.17);

    const seed = () => {
      const n = NODE_COUNT();
      nodes = Array.from({ length: n }, () => ({
        x: Math.random(),
        y: Math.random(),
        // Slow, calm drift — subtle enough to sit behind the headline without drawing the eye.
        vx: (Math.random() - 0.5) * 0.008,
        vy: (Math.random() - 0.5) * 0.008,
        z: 0.4 + Math.random() * 0.6,
      }));
      pulses = Array.from({ length: Math.max(2, Math.floor(n / 12)) }, () => spawnPulse());
    };

    const spawnPulse = (): Pulse => {
      const a = Math.floor(Math.random() * Math.max(1, nodes.length));
      return { a, b: a, t: 1, speed: 0.05 + Math.random() * 0.12 };
    };

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const rect = parent.getBoundingClientRect();
      width = Math.max(1, rect.width);
      height = Math.max(1, rect.height);
      // Smaller monospace cells → finer, less chunky ASCII texture.
      cell = width < 640 ? 17 : 13;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.font = `${cell}px "Geist Mono", ui-monospace, monospace`;
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      cols = Math.ceil(width / cell) + 1;
      rows = Math.ceil(height / cell) + 1;
      intensity = new Float32Array(cols * rows);
      if (nodes.length === 0) seed();
    };

    // Additive splat into the intensity grid (with soft bilinear-ish spread).
    const add = (gx: number, gy: number, v: number) => {
      const ix = Math.round(gx);
      const iy = Math.round(gy);
      if (ix < 0 || iy < 0 || ix >= cols || iy >= rows) return;
      intensity[iy * cols + ix] += v;
    };

    const step = (dt: number) => {
      for (const nd of nodes) {
        nd.x += nd.vx * dt;
        nd.y += nd.vy * dt;
        // Soft wrap-bounce inside the field.
        if (nd.x < 0 || nd.x > 1) nd.vx *= -1;
        if (nd.y < 0 || nd.y > 1) nd.vy *= -1;
        nd.x = Math.max(0, Math.min(1, nd.x));
        nd.y = Math.max(0, Math.min(1, nd.y));
      }
    };

    let lastTime = performance.now();

    const render = (now: number = performance.now()) => {
      // Frame-rate independent: normalize to ~60fps units so a 120Hz display doesn't run the
      // field twice as fast. Clamp the gap so returning to a backgrounded tab doesn't jump.
      const dtMs = Math.min(Math.max(now - lastTime, 0), 50);
      lastTime = now;
      const dt = dtMs / 16.6667;
      const dtSec = dtMs / 1000;

      intensity.fill(0);
      ctx.clearRect(0, 0, width, height);

      // Parallax: shift the whole field slightly opposite the pointer for depth.
      const px = (pointer.x - 0.5) * 0.04;
      const py = (pointer.y - 0.5) * 0.04;
      const gxOf = (n: Node) => (n.x - px * n.z) * (cols - 1);
      const gyOf = (n: Node) => (n.y - py * n.z) * (rows - 1);

      // Edges → intensity grid.
      const link = LINK_DIST();
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d = Math.sqrt(dx * dx + dy * dy);
          if (d > link) continue;
          const strength = (1 - d / link) * 0.5;
          const ax = gxOf(a);
          const ay = gyOf(a);
          const bx = gxOf(b);
          const by = gyOf(b);
          const steps = Math.max(2, Math.floor(d * (cols + rows) * 0.5));
          for (let s = 0; s <= steps; s++) {
            const f = s / steps;
            add(ax + (bx - ax) * f, ay + (by - ay) * f, strength);
          }
        }
      }

      // Nodes → a small bright cross in the grid.
      for (const n of nodes) {
        const gx = gxOf(n);
        const gy = gyOf(n);
        add(gx, gy, 1.4 * n.z);
      }

      // Paint the mesh grid, over a faint drifting ambient texture so the whole field reads as
      // ASCII (not a few dots) while the graph edges/nodes sit brighter on top.
      for (let gy = 0; gy < rows; gy++) {
        for (let gx = 0; gx < cols; gx++) {
          // Larger wavelength (smaller multipliers) → a slower, calmer shimmer.
          const ambient =
            (Math.sin(gx * 0.1 + t) + Math.cos(gy * 0.11 - t * 0.7) + 2) / 4; // 0..1, slow
          const v = intensity[gy * cols + gx] + ambient * 0.16;
          if (v < 0.12) continue;
          const clamped = Math.min(1, v);
          const char = MESH[Math.min(MESH.length - 1, Math.floor(clamped * MESH.length))];
          // Cool slate mesh, kept subtle so it never competes with the headline; brighter cores
          // (graph nodes/edges) tend toward white.
          const a = 0.04 + clamped * 0.3;
          const tone = 150 + Math.floor(clamped * 70);
          ctx.fillStyle = `rgba(${tone}, ${tone + 12}, ${tone + 30}, ${a})`;
          ctx.fillText(char, gx * cell, gy * cell);
        }
      }

      // Signal pulses along edges — the "agentic" message-passing, in cyan on top. Fewer, slower,
      // and dimmer than a plain particle demo so they read as an occasional flicker, not traffic.
      for (const p of pulses) {
        p.t += p.speed * dtSec;
        if (p.t >= 1 || p.a >= nodes.length) {
          // Pick a new edge: a random node → a nearby neighbor.
          const a = Math.floor(Math.random() * nodes.length);
          let best = -1;
          let bestD = Infinity;
          for (let j = 0; j < nodes.length; j++) {
            if (j === a) continue;
            const dx = nodes[a].x - nodes[j].x;
            const dy = nodes[a].y - nodes[j].y;
            const d = dx * dx + dy * dy;
            if (d < bestD && Math.random() > 0.5) {
              bestD = d;
              best = j;
            }
          }
          p.a = a;
          p.b = best === -1 ? a : best;
          p.t = 0;
        }
        const a = nodes[p.a];
        const b = nodes[p.b];
        if (!a || !b) continue;
        const gx = gxOf(a) + (gxOf(b) - gxOf(a)) * p.t;
        const gy = gyOf(a) + (gyOf(b) - gyOf(a)) * p.t;
        const fade = Math.sin(p.t * Math.PI); // fade in/out along the trip
        ctx.fillStyle = `rgba(34, 211, 238, ${0.1 + fade * 0.45})`;
        ctx.fillText("+", gx * cell, gy * cell);
      }

      t += (reduced ? 0.001 : 0.005) * dt;
      if (!reduced) step(dt);
      raf = requestAnimationFrame(render);
    };

    const onMove = (e: MouseEvent) => {
      const rect = parent.getBoundingClientRect();
      pointer.x = (e.clientX - rect.left) / rect.width;
      pointer.y = (e.clientY - rect.top) / rect.height;
    };

    resize();
    render();

    const ro = new ResizeObserver(resize);
    ro.observe(parent);
    window.addEventListener("mousemove", onMove, { passive: true });
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
      window.removeEventListener("mousemove", onMove);
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
