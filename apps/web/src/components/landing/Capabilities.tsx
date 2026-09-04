import type { ReactNode } from "react";

import { VideoPreview } from "@/components/landing/VideoPreview";
import { Reveal, Stagger, StaggerItem } from "@/components/landing/motion";
import { Section } from "@/components/site/Section";
import { GridLines } from "@/components/spectra/GridLines";
import { SectionHeading } from "@/components/spectra/SectionHeading";
import { SectionLabel } from "@/components/spectra/SectionLabel";
import { cn } from "@/lib/utils";

/**
 * Capabilities — a bento of what the canvas can actually render: image generation, 3D, video,
 * text-to-speech and RAG. Each tile is a real node type on the canvas (its mono chip names
 * it), not marketing abstraction.
 *
 * The visual language is "a fragment of the product, floating": every tile stages a small,
 * plausible piece of UI — a render frame, a viewport, a transport bar, a pipeline — on a
 * near-black card lit by one soft overhead spotlight, with the copy anchored beneath it.
 *
 * Two tiles show real output (`public/capability-image.jpg`, `public/capability-video.mp4`);
 * the rest are inline SVG/CSS, decorative and aria-hidden, and never a canvas/WebGL layer (one
 * of those once swallowed clicks across the whole page). Every tile is still at rest and
 * resolves on hover. That motion lives in CSS keyframes gated on `.group:hover` (globals.css)
 * or, for the video, in one small client leaf — nothing animates per-frame in React here.
 */

/* ---------------------------------------------------------------- primitives */

/** The tile shell: near-black surface, one hairline of light along the top edge, and an
 *  overhead spotlight that warms on hover. Everything else composes inside it. */
function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      data-capability-card
      className={cn(
        "group relative flex h-full flex-col overflow-hidden rounded-[24px]",
        // Spectra card anatomy: flat ink fill, a hairline border that goes green on hover,
        // and an inset top highlight. Never a drop shadow on a dark surface.
        "border border-[var(--border-dark)] bg-[var(--surface-card-dark)] shadow-[var(--inner-hairline)]",
        "transition-colors duration-200 ease-[var(--ease-standard)] hover:border-[var(--border-accent)]",
        className,
      )}
    >
      {/* top keyline */}
      <span
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 z-10 h-px bg-gradient-to-r from-transparent via-white/25 to-transparent opacity-70 transition-opacity duration-500 group-hover:opacity-100"
      />
      {/* overhead spotlight */}
      <span
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-80 w-[130%] -translate-x-1/2 rounded-[100%] bg-[radial-gradient(closest-side,rgba(255,255,255,0.11),transparent)] opacity-70 transition-opacity duration-700 group-hover:opacity-100"
      />
      {/* the same light again in brand green, only on hover — a tint, not a colour wash */}
      <span
        aria-hidden
        className="pointer-events-none absolute -top-40 left-1/2 h-80 w-[130%] -translate-x-1/2 rounded-[100%] bg-[radial-gradient(closest-side,rgba(62,206,139,0.16),transparent)] opacity-0 transition-opacity duration-700 group-hover:opacity-100"
      />
      {children}
    </div>
  );
}

/** The area a mockup floats in: generous headroom, no fixed height (a fixed one used to crop
 *  the panels' own footers mid-row), and a hair of lift on hover. */
function Stage({
  className,
  interactive = false,
  children,
}: {
  className?: string;
  /** Drops `aria-hidden`/`pointer-events-none` for the one tile that holds a real control. */
  interactive?: boolean;
  children: ReactNode;
}) {
  return (
    <div
      aria-hidden={interactive ? undefined : true}
      className={cn(
        "relative flex items-start justify-center px-6 pb-2 pt-9",
        !interactive && "pointer-events-none",
        "transition-transform duration-700 ease-out group-hover:-translate-y-1",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** A floating surface inside a Stage — the mockups' shared chrome. */
function Panel({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div
      className={cn(
        "rounded-xl border border-white/10 bg-white/[0.045] shadow-[0_28px_60px_-28px_rgba(0,0,0,0.95)]",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** A panel's title bar: two dots and a mono filename, the way every window in this app looks. */
function PanelBar({ label, right }: { label: string; right?: ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 border-b border-white/10 px-3 py-2">
      <span className="h-1.5 w-1.5 rounded-full bg-white/25" />
      <span className="h-1.5 w-1.5 rounded-full bg-white/15" />
      <span className="ml-1.5 font-mono text-[10px] tracking-tight text-white/45">{label}</span>
      {right ? <span className="ml-auto">{right}</span> : null}
    </div>
  );
}

function Copy({ chip, title, body }: { chip: string; title: string; body: string }) {
  return (
    <div className="relative flex flex-1 flex-col justify-end p-6">
      <span className="font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--accent-on-dark)]">
        {chip}
      </span>
      {/* Card titles are the one place the type steps up to medium (500); everything larger
          than this on the page is set light. */}
      <h3 className="mt-2.5 text-xl font-medium tracking-[-0.02em] text-[var(--text-on-dark)]">{title}</h3>
      <p className="mt-2 max-w-md text-[15px] leading-[1.55] text-[var(--text-on-dark-muted)]">{body}</p>
    </div>
  );
}

function Tile({
  chip,
  title,
  body,
  className,
  children,
}: {
  chip: string;
  title: string;
  body: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <StaggerItem className={cn("min-w-0", className)}>
      <Card>
        {children}
        <Copy chip={chip} title={title} body={body} />
      </Card>
    </StaggerItem>
  );
}

/* ------------------------------------------------------------------ visuals */

/** Image: the prompt at the bottom being resolved into the picture above it — one real render
 *  (`public/capability-image.jpg`), shown twice. The base copy is the latent state: blurred,
 *  desaturated and dark under a noise field, which is what "not generated yet" looks like. The
 *  scan window holds the same file untouched, so the head passing over it resolves noise into
 *  colour rather than crossfading between two different pictures.
 *
 *  The whole thing is CSS: the window is `h-0` at rest and its hover animation is `forwards`, so
 *  one sweep runs and then *holds* the finished frame for as long as you stay — a render
 *  completing, not a loop. Leaving the card drops the rule and it returns to latent.
 */
function ImageVisual() {
  return (
    <Stage>
      <Panel className="w-full max-w-[18rem] overflow-hidden">
        <PanelBar
          label="image"
          right={
            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[9px] text-white/50">
              gpt-image-1
            </span>
          }
        />
        <div className="relative h-40 overflow-hidden bg-black/40">
          {/* latent: the picture is in there, it just hasn't resolved */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/capability-image.jpg"
            alt=""
            aria-hidden
            loading="lazy"
            decoding="async"
            className="absolute inset-0 h-full w-full scale-105 object-cover opacity-60 blur-[6px] grayscale"
          />
          {/* the noise it is buried in */}
          <span
            aria-hidden
            className="absolute inset-0 opacity-70"
            style={{
              backgroundImage: "radial-gradient(rgba(255,255,255,0.14) 1px, transparent 1px)",
              backgroundSize: "8px 8px",
            }}
          />

          {/* everything the scan head has already passed */}
          <div className="scan-window absolute inset-x-0 top-0 h-0 overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/capability-image.jpg"
              alt="A cat, generated on the canvas"
              loading="lazy"
              decoding="async"
              className="absolute inset-x-0 top-0 h-40 w-full object-cover"
            />
            <span aria-hidden className="scan-head absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-brand/25 to-transparent" />
            <span aria-hidden className="scan-head absolute inset-x-0 bottom-0 h-px bg-brand shadow-[0_0_12px_2px_rgba(62,206,139,0.6)]" />
          </div>

          {/* viewfinder corners */}
          <span aria-hidden className="absolute left-2 top-2 h-3 w-3 border-l border-t border-brand/70" />
          <span aria-hidden className="absolute right-2 top-2 h-3 w-3 border-r border-t border-brand/70" />
          <span aria-hidden className="absolute bottom-2 left-2 h-3 w-3 border-b border-l border-brand/70" />
          <span aria-hidden className="absolute bottom-2 right-2 h-3 w-3 border-b border-r border-brand/70" />
        </div>
        {/* the prompt it is resolving */}
        <div className="flex items-center gap-2 border-t border-white/10 px-3 py-2">
          <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-white/30">prompt</span>
          <span className="truncate font-mono text-[10px] text-white/55">a tabby cat, portra 400</span>
          <span className="h-3 w-px shrink-0 bg-brand" />
        </div>
      </Panel>
    </Stage>
  );
}

/** 3D: a wireframe cube in a viewport, sitting on a receding ground grid. Six faces and eight
 *  vertices composed in real CSS 3D (`.mesh-cube`, keyframed in globals.css) so hovering orbits
 *  it properly instead of spinning a flat drawing. */
function MeshVisual() {
  /** Half the edge length, in px — the faces push out to it, the vertices sit on its corners. */
  const S = 42;
  const faces = [
    `translateZ(${S}px)`,
    `rotateY(180deg) translateZ(${S}px)`,
    `rotateY(90deg) translateZ(${S}px)`,
    `rotateY(-90deg) translateZ(${S}px)`,
    `rotateX(90deg) translateZ(${S}px)`,
    `rotateX(-90deg) translateZ(${S}px)`,
  ];
  const verts = [-1, 1].flatMap((x) => [-1, 1].flatMap((y) => [-1, 1].map((z) => [x, y, z])));
  return (
    <Stage>
      <Panel className="w-full max-w-[18rem] overflow-hidden">
        <PanelBar label="viewport" right={<span className="font-mono text-[9px] text-white/35">orbit</span>} />
        <div className="relative h-40 overflow-hidden">
          {/* ground grid, receding */}
          <span
            className="absolute inset-x-0 bottom-0 h-16 opacity-40 [mask-image:linear-gradient(to_top,black,transparent)]"
            style={{
              backgroundImage:
                "linear-gradient(rgba(255,255,255,0.18) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.18) 1px,transparent 1px)",
              backgroundSize: "18px 12px",
            }}
          />
          {/* the object's own light, behind the faces */}
          <span className="absolute left-1/2 top-1/2 h-28 w-28 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(62,206,139,0.22),transparent)]" />
          <div className="absolute inset-0 flex items-center justify-center [perspective:520px]">
            <div className="mesh-cube relative" style={{ width: S * 2, height: S * 2 }}>
              {faces.map((transform) => (
                <span
                  key={transform}
                  className="absolute inset-0 border border-white/20 bg-brand/[0.04]"
                  style={{ transform }}
                />
              ))}
              {verts.map(([x, y, z]) => (
                <span
                  key={`${x}${y}${z}`}
                  className="absolute left-1/2 top-1/2 -ml-[3px] -mt-[3px] h-1.5 w-1.5 rounded-full bg-brand"
                  style={{ transform: `translate3d(${x * S}px, ${y * S}px, ${z * S}px)` }}
                />
              ))}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 border-t border-white/10 px-3 py-2">
          <span className="font-mono text-[9px] text-white/45">mesh.glb</span>
          <span className="ml-auto rounded-full border border-white/10 bg-white/[0.06] px-2 py-0.5 font-mono text-[9px] text-white/55">
            download
          </span>
        </div>
      </Panel>
    </Stage>
  );
}

/** Voice: a transport bar — white play button, equalizer, model chip. Bars bounce on hover. */
function WaveVisual() {
  const bars = Array.from({ length: 26 }, (_, i) => {
    const t = i / 25;
    const env = Math.sin(t * Math.PI);
    const wobble = 0.4 + 0.6 * Math.abs(Math.sin(i * 2.7));
    return Math.max(0.14, env * wobble);
  });
  return (
    <Stage>
      <Panel className="w-full max-w-[18rem] overflow-hidden">
        <PanelBar label="speech.mp3" right={<span className="font-mono text-[9px] text-white/35">0:07</span>} />
        <div className="flex h-40 items-center gap-3 px-4">
          {/* the one bright element on the card, the way the reference lights a single control */}
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white shadow-[0_8px_20px_-6px_rgba(255,255,255,0.5)]">
            <svg viewBox="0 0 12 12" className="h-3 w-3 fill-black">
              <path d="M3 1.5 10 6 3 10.5Z" />
            </svg>
          </span>
          <span className="flex h-12 flex-1 items-center justify-between gap-[2px]">
            {bars.map((h, i) => (
              <span
                key={i}
                className="eq-bar w-[3px] rounded-full bg-brand/70"
                style={{ height: `${h * 100}%`, "--eq-delay": `${(i % 7) * 0.09}s` } as React.CSSProperties}
              />
            ))}
          </span>
        </div>
        <div className="border-t border-white/10 px-3 py-2">
          <span className="font-mono text-[9px] text-white/45">gpt-4o-mini-tts</span>
        </div>
      </Panel>
    </Stage>
  );
}

/** Video: the Image tile's still, now a clip you can actually play. Same panel geometry as the
 *  Image tile — bar, frame, status row — because it is meant to read as the next step in one
 *  pipeline rather than a different kind of card. */
function VideoVisual() {
  return (
    <Stage interactive>
      <Panel className="w-full max-w-[18rem] overflow-hidden">
        <PanelBar
          label="shot_01.mp4"
          right={
            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[9px] text-white/50">
              seedance
            </span>
          }
        />
        <VideoPreview />
      </Panel>
    </Stage>
  );
}

/* The Knowledge tile's pipeline, in one coordinate system.
 *
 * Rails and chips used to be SVG-over-DOM, which meant every change to the tile's width was a
 * chance for the rails to stop meeting the chips (it happened twice). Everything is one SVG now
 * with uniform scaling, so the geometry can only be right or wrong once — and the glyphs are
 * hand-drawn at the same 1.25 stroke weight as the mesh and the cat rather than icon-font
 * imports at a different weight. */

/** Rail geometry, shared by the drawn path and by the particle that travels it. */
const RAG_INGEST = [
  "M57 44 C 120 44, 132 95, 188 95",
  "M57 95 H 188",
  "M57 146 C 120 146, 132 95, 188 95",
];
const RAG_STORE = "M232 95 H 361";

const RAG_GLYPHS = {
  file: (
    <>
      <path d="M-5 -7 h 6 l 4 4 v 10 h -10 z" />
      <path d="M1 -7 v 4 h 4" />
      <path d="M-2.5 1.5 h 5" />
      <path d="M-2.5 4.5 h 5" />
    </>
  ),
  note: (
    <>
      <path d="M-6 -6 h 12 v 7 l -5 5 h -7 z" />
      <path d="M6 1 h -5 v 5" />
      <path d="M-3 -3 h 6" />
      <path d="M-3 0 h 4" />
    </>
  ),
  globe: (
    <>
      <circle cx="0" cy="0" r="6.5" />
      <path d="M0 -6.5 C -3.6 -3, -3.6 3, 0 6.5 C 3.6 3, 3.6 -3, 0 -6.5" />
      <path d="M-6.2 -2 H 6.2" />
      <path d="M-6.2 2 H 6.2" />
    </>
  ),
  database: (
    <>
      <path d="M-6 -6 a 6 2.6 0 1 0 12 0 a 6 2.6 0 1 0 -12 0" />
      <path d="M-6 -6 V 5 a 6 2.6 0 0 0 12 0 V -6" />
      <path d="M-6 -0.5 a 6 2.6 0 0 0 12 0" />
    </>
  ),
} as const;

/** A source or sink on the pipeline: a bordered disc with a glyph, drawn at `x`/`y`. */
function RagChip({
  x,
  y,
  glyph,
  r = 17,
  accent = false,
}: {
  x: number;
  y: number;
  glyph: keyof typeof RAG_GLYPHS;
  r?: number;
  accent?: boolean;
}) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle
        r={r}
        fill="rgba(255,255,255,0.05)"
        stroke={accent ? "rgba(62,206,139,0.4)" : "rgba(255,255,255,0.13)"}
        strokeWidth="1"
      />
      <g
        fill="none"
        stroke={accent ? "rgba(62,206,139,0.85)" : "rgba(255,255,255,0.55)"}
        strokeWidth="1.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {RAG_GLYPHS[glyph]}
      </g>
    </g>
  );
}

/** Knowledge: your files flowing through the embedding model into the vector store. The dots
 *  ride the same path data the rails are drawn from (CSS `offset-path`), so a rail and its
 *  traffic can never disagree; the outbound dots are phase-shifted half a cycle so material
 *  appears to leave the model as more arrives. */
function RagVisual() {
  return (
    <Stage>
      <div className="relative h-56 w-full max-w-[31rem]">
        <svg viewBox="0 0 420 190" className="h-full w-full">
          {/* rails */}
          {[...RAG_INGEST, RAG_STORE].map((d) => (
            <path key={d} d={d} fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="1" strokeDasharray="3 4" />
          ))}
          {/* direction, still legible when nothing is moving */}
          {[
            "M181 91 l 5 4 l -5 4",
            "M354 91 l 5 4 l -5 4",
          ].map((d) => (
            <path key={d} d={d} fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" />
          ))}

          {/* sources */}
          <RagChip x={40} y={44} glyph="file" />
          <RagChip x={40} y={95} glyph="note" />
          <RagChip x={40} y={146} glyph="globe" />

          {/* the model: falloff rings, a pulse on the beat of the flow, then the core */}
          <g transform="translate(210 95)">
            <circle r="38" fill="none" stroke="rgba(255,255,255,0.05)" />
            <circle r="28" fill="rgba(62,206,139,0.05)" stroke="rgba(255,255,255,0.09)" />
            <circle className="rag-pulse" r="20" fill="none" stroke="rgba(62,206,139,0.5)" strokeWidth="1" />
            <circle r="20" fill="rgba(62,206,139,0.14)" stroke="rgba(62,206,139,0.45)" strokeWidth="1" />
            <path
              d="M0 -9 C 1.2 -3.4, 3.4 -1.2, 9 0 C 3.4 1.2, 1.2 3.4, 0 9 C -1.2 3.4, -3.4 1.2, -9 0 C -3.4 -1.2, -1.2 -3.4, 0 -9 Z"
              fill="none"
              stroke="#3ece8b"
              strokeWidth="1.25"
              strokeLinejoin="round"
            />
          </g>

          {/* the store */}
          <RagChip x={380} y={95} glyph="database" r={19} accent />

          {/* traffic — ingest staggered across the three rails, then out to the store */}
          {RAG_INGEST.map((d, i) => (
            <circle
              key={`in-${d}`}
              className="rag-dot"
              r="2.75"
              fill="#3ece8b"
              style={{ offsetPath: `path("${d}")`, animationDelay: `${i * 0.93}s` }}
            />
          ))}
          {[0.46, 1.39, 2.32].map((delay) => (
            <circle
              key={`out-${delay}`}
              className="rag-dot"
              r="2.75"
              fill="#3ece8b"
              style={{ offsetPath: `path("${RAG_STORE}")`, animationDelay: `${delay}s` }}
            />
          ))}

          {/* what each stage is */}
          <g className="font-mono fill-white/30 text-[9px]" textAnchor="middle">
            <text x="40" y="180">sources</text>
            <text x="210" y="180">embed</text>
            <text x="380" y="180">pgvector</text>
          </g>
        </svg>
      </div>
    </Stage>
  );
}

/* -------------------------------------------------------------------- section */

export function Capabilities() {
  return (
    <Section id="features" className="relative isolate">
      <GridLines />
      {/* Asymmetric two-column opener: label + heading left, the supporting paragraph right.
          It's the shape every Spectra section starts with. */}
      <Reveal>
        <div className="grid items-start gap-10 lg:grid-cols-2">
          <div>
            <SectionLabel index="02">what you can build</SectionLabel>
            {/* Two-tone: neutral phrase, then the green one. */}
            <SectionHeading className="mt-6" size="display" accent="Ship it.">
              Speak it. Search it. Render it.
            </SectionHeading>
          </div>
          <p className="max-w-[430px] text-pretty text-lg leading-[1.55] text-[var(--text-on-dark-muted)] lg:pt-16">
            One canvas for learners, creatives and builders — voice, retrieval, images, video and
            3D are nodes you wire together, not products you subscribe to separately.
          </p>
        </div>
        <p className="mt-10 font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--text-on-dark-faint)]">
          01 draw the graph <span className="text-[var(--accent-on-dark)]">·</span> 02 run &amp;
          inspect <span className="text-[var(--accent-on-dark)]">·</span> 03 own the code
        </p>
      </Reveal>

      <Stagger className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-12">
        <Tile
          chip="image"
          title="Image generation"
          body="Prompt to picture with the gpt-image family — or route through a film-grain style agent first."
          className="lg:col-span-4"
        >
          <ImageVisual />
        </Tile>

        <Tile
          chip="3d"
          title="3D generation"
          body="Image to mesh on fal — describe an object, download the GLB."
          className="lg:col-span-4"
        >
          <MeshVisual />
        </Tile>

        <Tile
          chip="voice"
          title="Text to speech"
          body="Agents that talk back — gpt-4o-mini-tts up to tts-1-hd."
          className="lg:col-span-4"
        >
          <WaveVisual />
        </Tile>

        <Tile
          chip="video"
          title="Video generation"
          body="Seedance on fal — write a shot, or animate a still the Image node just made. Plus, billed in credits."
          className="lg:col-span-5"
        >
          <VideoVisual />
        </Tile>

        <Tile
          chip="knowledge"
          title="RAG on your notes"
          body="A Knowledge node retrieves from your own material — pgvector or the built-in demo source."
          className="sm:col-span-2 lg:col-span-7"
        >
          <RagVisual />
        </Tile>

      </Stagger>
    </Section>
  );
}
