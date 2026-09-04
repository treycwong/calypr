/**
 * Deterministic generative art for a landing template card — a green-clamped fork of the
 * dashboard's ProjectArt. Same FNV-1a + mulberry32 machinery (deterministic, so a card never
 * flickers between renders), but where the dashboard wants every project to look *different*,
 * the landing wants every card to look like *one brand*: hues are pinned to the green band with
 * a cooler drift, and a small node-graph motif — dots joined by hairline strokes, one lit in
 * the brand green — echoes the canvas the cards are selling.
 *
 * Pure SVG computed once per render; no "use client", so it costs nothing on the wire.
 */

function hash(seed: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

function rng(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function TemplateArt({ seed }: { seed: string }) {
  const random = rng(hash(seed));
  const pick = (min: number, max: number) => min + random() * (max - min);

  // Green band (≈140–170, centred on Spectra's green-400 at 152) with an occasional drift
  // toward teal — never off-brand. It was the cyan band until the brand moved.
  const hues = [pick(140, 168), pick(148, 178), pick(132, 160)];
  const blobs = hues.map((h, i) => ({
    id: `${seed}-b${i}`,
    cx: pick(-10, 110),
    cy: pick(-10, 110),
    r: pick(45, 95),
    color: `hsl(${h} ${pick(40, 70)}% ${pick(35, 55)}%)`,
    opacity: pick(0.3, 0.55),
  }));

  // The node-graph motif: a loose left-to-right chain of 4–5 nodes, one lit green.
  const count = 4 + Math.floor(random() * 2);
  const nodes = Array.from({ length: count }, (_, i) => ({
    x: 12 + (76 / (count - 1)) * i + pick(-5, 5),
    y: pick(30, 70),
  }));
  const lit = Math.floor(random() * count);

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="xMidYMid slice"
      className="h-full w-full"
      aria-hidden
    >
      <defs>
        {blobs.map((b) => (
          <radialGradient key={b.id} id={b.id}>
            <stop offset="0%" stopColor={b.color} stopOpacity={b.opacity} />
            <stop offset="100%" stopColor={b.color} stopOpacity={0} />
          </radialGradient>
        ))}
      </defs>

      <rect width="100" height="100" fill="#0b0b0e" />
      {blobs.map((b) => (
        <circle key={b.id} cx={b.cx} cy={b.cy} r={b.r} fill={`url(#${b.id})`} />
      ))}
      <rect width="100" height="100" fill="#0b0b0e" opacity="0.35" />

      {nodes.slice(0, -1).map((n, i) => (
        <line
          key={`l${i}`}
          x1={n.x}
          y1={n.y}
          x2={nodes[i + 1].x}
          y2={nodes[i + 1].y}
          stroke="rgba(255,255,255,0.25)"
          strokeWidth="0.5"
        />
      ))}
      {nodes.map((n, i) => (
        <circle
          key={`n${i}`}
          cx={n.x}
          cy={n.y}
          r={i === lit ? 2.4 : 1.6}
          fill={i === lit ? "#3ece8b" : "rgba(255,255,255,0.55)"}
        />
      ))}
      {/* soft halo around the lit node */}
      <circle cx={nodes[lit].x} cy={nodes[lit].y} r={6} fill="#3ece8b" opacity="0.18" />
    </svg>
  );
}
