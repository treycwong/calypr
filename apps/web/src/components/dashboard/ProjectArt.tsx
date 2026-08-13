"use client";

/**
 * A deterministic piece of generative art per project, for its dashboard card.
 *
 * The card used to draw the project's actual graph. That was accurate and unhelpful: most graphs
 * are a short line of dots, so every card looked like every other card, and the one thing a
 * dashboard has to do — let you find a project at a glance — it did worst.
 *
 * This does the opposite. It carries no information about the graph, and is therefore free to be
 * *distinctive*: seeded only by the project id, so a project's art never changes, and two
 * projects are near-certain to look nothing alike. The name underneath is what you read; the art
 * is what you recognise.
 *
 * Pure SVG with no runtime dependency — a handful of gradients and strokes, computed once per
 * render from the seed.
 */

/** FNV-1a. Small, fast, and stable across runs — `String.prototype.hashCode` this is not. */
function hash(seed: string): number {
  let h = 0x811c9dc5;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/** mulberry32: a tiny seeded PRNG. Deterministic, so the same project always draws the same art. */
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

export function ProjectArt({ seed }: { seed: string }) {
  const random = rng(hash(seed));
  const pick = (min: number, max: number) => min + random() * (max - min);

  // One hue anchors the piece and the others sit near it, so a card reads as a single palette
  // rather than a clash. Saturation stays high and lightness mid — these sit on near-black, and
  // anything muted disappears into it.
  const base = Math.floor(random() * 360);
  const hues = [base, (base + pick(25, 65)) % 360, (base + pick(180, 240)) % 360];

  // Soft colour fields. Radii are generous and centres can sit outside the frame, which is what
  // keeps the composition from looking like three circles in a box.
  const blobs = hues.map((h, i) => ({
    id: `${seed}-b${i}`,
    cx: pick(-10, 110),
    cy: pick(-10, 110),
    r: pick(45, 95),
    color: `hsl(${h} 85% ${pick(45, 65)}%)`,
    opacity: pick(0.35, 0.7),
  }));

  // A few long strokes over the fields, drifting in one direction, to give the piece some
  // structure. Same hues, high lightness, low opacity — they read as light, not as lines.
  const strokeCount = Math.floor(pick(3, 7));
  const drift = pick(-30, 30);
  const strokes = Array.from({ length: strokeCount }, (_, i) => {
    const y = pick(-5, 105);
    return {
      key: i,
      d: `M -10 ${y} C ${pick(15, 40)} ${y + drift}, ${pick(60, 85)} ${y - drift}, 110 ${pick(-5, 105)}`,
      color: `hsl(${hues[i % hues.length]} 90% 80%)`,
      opacity: pick(0.08, 0.22),
      width: pick(0.6, 2.4),
    };
  });

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="xMidYMid slice"
      className="h-full w-full"
      aria-hidden
      data-testid="project-art"
    >
      <defs>
        {blobs.map((b) => (
          // Fading each field to transparent is what makes them blend instead of overlap.
          <radialGradient key={b.id} id={b.id}>
            <stop offset="0%" stopColor={b.color} stopOpacity={b.opacity} />
            <stop offset="100%" stopColor={b.color} stopOpacity={0} />
          </radialGradient>
        ))}
      </defs>

      {/* Near-black ground, so a card is legible before any of the colour lands. */}
      <rect width="100" height="100" fill="#0b0b0e" />
      {blobs.map((b) => (
        <circle key={b.id} cx={b.cx} cy={b.cy} r={b.r} fill={`url(#${b.id})`} />
      ))}
      {strokes.map((s) => (
        <path
          key={s.key}
          d={s.d}
          fill="none"
          stroke={s.color}
          strokeOpacity={s.opacity}
          strokeWidth={s.width}
          vectorEffect="non-scaling-stroke"
        />
      ))}
      {/* A dark wash over the whole thing keeps every card in the same tonal range — without it,
          a card that happened to seed bright colours shouted over its neighbours. */}
      <rect width="100" height="100" fill="#0b0b0e" opacity="0.25" />
    </svg>
  );
}
