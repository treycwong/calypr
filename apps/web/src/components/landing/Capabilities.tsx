import type { ReactNode } from "react";

import { TemplateArt } from "@/components/landing/TemplateArt";
import { Reveal, Stagger, StaggerItem } from "@/components/landing/motion";
import { Eyebrow } from "@/components/site/Eyebrow";
import { Section } from "@/components/site/Section";
import { cn } from "@/lib/utils";

/**
 * Capabilities — a bento of what the canvas can actually render: image generation, 3D, video,
 * text-to-speech, RAG, and the code you take with you. Each tile is a real node type on the
 * canvas (its mono chip names it), not marketing abstraction. All visuals are inline SVG/CSS —
 * decorative, aria-hidden, and never a canvas/WebGL layer (one of those once swallowed clicks
 * across the whole page).
 */

const AGENT_SNIPPET = `def node_agent(state: State) -> dict:
    model = init_chat_model("gpt-4o-mini").bind_tools([web_search])
    reply = model.invoke([SystemMessage(content=system), *state["messages"]])
    return {"messages": [reply]}`;

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
    <StaggerItem
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-xl border border-border bg-card/30",
        // cyan keyline along the top edge, brightening on hover
        "before:absolute before:inset-x-0 before:top-0 before:z-10 before:h-px before:bg-gradient-to-r before:from-brand/0 before:via-brand/40 before:to-brand/0 before:opacity-60 before:transition-opacity before:duration-500 hover:before:opacity-100",
        className,
      )}
    >
      {children}
      <div className="relative flex flex-1 flex-col justify-end p-6">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-brand/80">
          {chip}
        </span>
        <h3 className="mt-2 text-lg font-medium tracking-tight">{title}</h3>
        <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted-foreground">{body}</p>
      </div>
    </StaggerItem>
  );
}

/** Wireframe polyhedron for the 3D tile — 1px strokes, cyan vertices. */
function MeshVisual() {
  const verts: [number, number][] = [
    [60, 8],
    [104, 34],
    [96, 84],
    [48, 100],
    [14, 62],
    [26, 24],
    [60, 52],
  ];
  const edges: [number, number][] = [
    [0, 1],
    [1, 2],
    [2, 3],
    [3, 4],
    [4, 5],
    [5, 0],
    [0, 6],
    [1, 6],
    [2, 6],
    [3, 6],
    [4, 6],
    [5, 6],
  ];
  return (
    <div aria-hidden className="pointer-events-none relative flex h-40 items-center justify-center sm:h-48">
      <svg
        viewBox="0 0 120 110"
        className="h-full w-auto opacity-80 transition-transform duration-700 group-hover:rotate-6"
      >
        {edges.map(([a, b], i) => (
          <line
            key={i}
            x1={verts[a][0]}
            y1={verts[a][1]}
            x2={verts[b][0]}
            y2={verts[b][1]}
            stroke="rgba(255,255,255,0.28)"
            strokeWidth="0.75"
          />
        ))}
        {verts.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={i === 6 ? 2.5 : 1.75} fill={i === 6 ? "#22d3ee" : "rgba(255,255,255,0.7)"} />
        ))}
        <circle cx={60} cy={52} r={9} fill="#22d3ee" opacity="0.15" />
      </svg>
    </div>
  );
}

/** Filmstrip for the Video tile — four frames, sprocket holes, and a playhead that sweeps on
 *  hover (`.playhead`, keyframed in globals.css). Each frame is one notch further into the same
 *  pan, so the strip reads as motion rather than four unrelated pictures. */
function FilmVisual() {
  const frames = [0, 1, 2, 3];
  return (
    <div aria-hidden className="pointer-events-none relative flex h-28 items-center justify-center px-6">
      <svg viewBox="0 0 220 78" className="h-full w-auto opacity-90">
        {/* sprocket rails */}
        {[4, 68].map((y) => (
          <g key={y}>
            {Array.from({ length: 11 }, (_, i) => (
              <rect
                key={i}
                x={8 + i * 19}
                y={y}
                width="7"
                height="6"
                rx="1.5"
                fill="none"
                stroke="rgba(255,255,255,0.22)"
                strokeWidth="0.75"
              />
            ))}
          </g>
        ))}
        {frames.map((f) => {
          const x = 10 + f * 51;
          return (
            <g key={f}>
              <rect x={x} y="16" width="46" height="46" rx="2" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="0.75" />
              {/* a horizon and a subject, nudged one step per frame — the pan */}
              <line x1={x + 5} y1="46" x2={x + 41} y2="46" stroke="rgba(255,255,255,0.16)" strokeWidth="0.75" />
              <circle cx={x + 14 + f * 5} cy="38" r="4" fill="#22d3ee" opacity={0.35 + f * 0.2} />
              <path
                d={`M${x + 5} 46 L${x + 17} 31 L${x + 27} 46 Z`}
                fill="none"
                stroke="rgba(255,255,255,0.24)"
                strokeWidth="0.75"
              />
            </g>
          );
        })}
      </svg>
      {/* The playhead. A DOM element rather than an SVG line so the CSS keyframe animates a
          compositor-only transform; `--playhead-travel` is the strip's width. */}
      <span
        className="playhead absolute bottom-3 left-6 top-3 w-px bg-brand"
        style={{ "--playhead-travel": "calc(100% - 3rem)" } as React.CSSProperties}
      />
    </div>
  );
}

/** Equalizer bars for the Voice tile — animates on hover via the `.eq-bar` CSS keyframe. */
function WaveVisual() {
  // deterministic pseudo-random heights, tallest mid-field
  const bars = Array.from({ length: 28 }, (_, i) => {
    const t = i / 27;
    const env = Math.sin(t * Math.PI);
    const wobble = 0.4 + 0.6 * Math.abs(Math.sin(i * 2.7));
    return Math.max(0.12, env * wobble);
  });
  return (
    <div aria-hidden className="pointer-events-none flex h-28 items-center justify-center gap-[3px] px-6">
      {bars.map((h, i) => (
        <span
          key={i}
          className="eq-bar w-[3px] rounded-full bg-brand/70"
          style={{ height: `${h * 100}%`, "--eq-delay": `${(i % 7) * 0.09}s` } as React.CSSProperties}
        />
      ))}
    </div>
  );
}

/** Document chunks flowing into a lit retrieval node, then out to an answer. */
function RagVisual() {
  return (
    <div aria-hidden className="pointer-events-none flex h-28 items-center justify-center">
      <svg viewBox="0 0 200 90" className="h-full w-auto opacity-90">
        {/* chunk stack */}
        {[14, 34, 54].map((y, i) => (
          <g key={i}>
            <rect x="12" y={y} width="34" height="14" rx="2" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="0.75" />
            {[4, 8].map((dy) => (
              <line key={dy} x1={17} y1={y + dy} x2={41} y2={y + dy} stroke="rgba(255,255,255,0.18)" strokeWidth="1" />
            ))}
          </g>
        ))}
        {/* paths to the retriever — the middle one is the hit */}
        <path d="M46 21 C 75 21, 80 45, 102 45" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.75" />
        <path d="M46 41 C 72 41, 82 45, 102 45" fill="none" stroke="#22d3ee" strokeWidth="1.25" opacity="0.9" />
        <path d="M46 61 C 75 61, 80 45, 102 45" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="0.75" />
        <circle cx="108" cy="45" r="5" fill="#22d3ee" />
        <circle cx="108" cy="45" r="11" fill="#22d3ee" opacity="0.15" />
        {/* onward to the answer */}
        <line x1="113" y1="45" x2="164" y2="45" stroke="rgba(255,255,255,0.3)" strokeWidth="0.75" strokeDasharray="3 3" />
        <rect x="164" y="36" width="24" height="18" rx="3" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="0.75" />
      </svg>
    </div>
  );
}

export function Capabilities() {
  return (
    <Section id="features">
      <Reveal className="max-w-3xl">
        <Eyebrow>what you can build</Eyebrow>
        <h2 className="mt-5 text-3xl font-semibold tracking-tight sm:text-5xl">
          Speak it. Search it. Render it. Ship it.
        </h2>
        <p className="mt-4 max-w-xl text-sm leading-relaxed text-muted-foreground sm:text-base">
          One canvas for learners, creatives and builders — voice, retrieval, images, video and
          3D are nodes you wire together, not products you subscribe to separately.
        </p>
        <p className="mt-6 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          01 draw the graph <span className="text-brand">·</span> 02 run &amp; inspect{" "}
          <span className="text-brand">·</span> 03 own the code
        </p>
      </Reveal>

      <Stagger className="mt-12 grid gap-4 lg:grid-cols-12">
        <Tile
          chip="image"
          title="Image generation"
          body="Prompt to picture with the gpt-image family — or route through a film-grain style agent first."
          className="lg:col-span-7"
        >
          <div aria-hidden className="pointer-events-none relative m-6 mb-0 h-44 overflow-hidden rounded-lg border border-border sm:h-52">
            <TemplateArt seed="capability-image-generation" />
            {/* viewfinder corners */}
            <span className="absolute left-2 top-2 h-3 w-3 border-l border-t border-brand/70" />
            <span className="absolute right-2 top-2 h-3 w-3 border-r border-t border-brand/70" />
            <span className="absolute bottom-2 left-2 h-3 w-3 border-b border-l border-brand/70" />
            <span className="absolute bottom-2 right-2 h-3 w-3 border-b border-r border-brand/70" />
          </div>
        </Tile>

        <Tile
          chip="3d"
          title="3D generation"
          body="Image to mesh on fal — describe an object, download the GLB."
          className="lg:col-span-5"
        >
          <div className="pt-6">
            <MeshVisual />
          </div>
        </Tile>

        <Tile
          chip="video"
          title="Video generation"
          body="Seedance on fal — write a shot, or animate a still the Image node just made. Plus, on your own fal key."
          className="lg:col-span-7"
        >
          <div className="pt-6">
            <FilmVisual />
          </div>
        </Tile>

        <Tile
          chip="voice"
          title="Text to speech"
          body="Agents that talk back — gpt-4o-mini-tts up to tts-1-hd."
          className="lg:col-span-5"
        >
          <div className="pt-6">
            <WaveVisual />
          </div>
        </Tile>

        <Tile
          chip="knowledge"
          title="RAG on your notes"
          body="A Knowledge node retrieves from your own material — pgvector or the built-in demo source."
          className="lg:col-span-6"
        >
          <div className="pt-6">
            <RagVisual />
          </div>
        </Tile>

        <Tile
          chip="code"
          title="Own the code"
          body="Every graph compiles to LangGraph Python. No ceiling, no lock-in."
          className="lg:col-span-6"
        >
          <div aria-hidden className="pointer-events-none m-6 mb-0 overflow-hidden rounded-lg border border-border bg-background/60">
            <div className="flex items-center gap-1.5 border-b border-border px-3 py-2">
              <span className="h-2 w-2 rounded-full border border-border" />
              <span className="h-2 w-2 rounded-full border border-border" />
              <span className="ml-2 font-mono text-[10px] text-muted-foreground">agent.py</span>
            </div>
            <pre className="overflow-hidden p-3 font-mono text-[10px] leading-relaxed text-muted-foreground">
              <code>{AGENT_SNIPPET}</code>
            </pre>
          </div>
        </Tile>
      </Stagger>
    </Section>
  );
}
