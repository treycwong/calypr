"use client";

import { Handle, type NodeProps, Position } from "@xyflow/react";
import { Download, Maximize2 } from "lucide-react";
import dynamic from "next/dynamic";
import { type ComponentType, type ReactNode, useState } from "react";

import { MediaViewer } from "@/components/MediaViewer";
import { downloadUrl, filenameFrom } from "@/lib/download";

import { NODE_STYLE } from "@/components/canvas/node-style";
import {
  type CalyprNodeType,
  type NodeData,
  type NodeStatus,
  isImageToVideo,
  routerHandleNames,
} from "@/lib/graph";
import { useConnectors } from "@/lib/use-connectors";

const handleStyle = { width: 10, height: 10 };

// Run-state styling, layered above the idle/selected border. `active` pulses (see canvas.css
// `nodePulse`); `done`/`error` settle to a persistent ring until the next run clears them.
const STATUS_CLASS: Record<NodeStatus, string> = {
  active:
    "border-state-running shadow-[0_0_0_1px_rgb(92_201_155),0_0_26px_-2px_rgb(92_201_155/0.6)] animate-[nodePulse_1.2s_ease-in-out_infinite]",
  // Done is deliberately colourless: green is "live", and a finished graph shouldn't look live.
  done: "border-white/35 shadow-[0_0_0_1px_rgb(243_245_248/0.12)]",
  error: "border-red-500 shadow-[0_0_0_1px_rgb(239_68_68/0.6)]",
};

function statusOf(data: unknown): NodeStatus | undefined {
  return (data as NodeData | undefined)?.status;
}

// Flow runs left → right: inputs enter on the Left, outputs leave on the Right.
function Shell({
  title,
  type,
  selected,
  status,
  testid,
  children,
}: {
  title: string;
  type: CalyprNodeType;
  selected?: boolean;
  status?: NodeStatus;
  testid?: string;
  children?: ReactNode;
}) {
  // The icon comes from the same map the Blocks palette reads, so the card you picked in the
  // sidebar is visibly the card that landed here. It replaced a 2px coloured dot whose colour was
  // hardcoded at each of the fourteen call sites — and it is monochrome, which leaves the canvas
  // free to use colour for run state alone (the green active glow; done settles to neutral).
  const { icon: Icon } = NODE_STYLE[type];
  // A run status takes visual priority over selection so you can watch execution move even while
  // a node is selected; otherwise fall back to the selected glow, then idle.
  // The background is part of this rather than a constant `bg-card` on the base class: two
  // background utilities on one element are decided by their order in Tailwind's output, not by
  // the class attribute, so the selected wash would win or lose unpredictably.
  const stateClass = status
    ? `bg-card ${STATUS_CLASS[status]}`
    : selected
      ? // Neutral, not green. Green is the running state on this canvas — using it for selection
        // too meant a selected node and a running node looked the same, and a graph you had
        // clicked around looked like it was mid-run.
        //
        // **Opaque.** This was a translucent white wash, which let the wires behind the card
        // show straight through it — selecting a node in a busy part of the graph made it
        // harder to read, not easier. A card is a solid object.
        "bg-neutral-700 border-white/60 shadow-[0_0_0_1px_rgb(255_255_255/0.25)]"
      : "bg-card border-white/[0.08] hover:border-white/20";
  return (
    <div
      data-testid={testid}
      data-status={status ?? undefined}
      // `transition-colors duration-75`, not a bare `transition`. The bare utility animates every
      // animatable property — box-shadow and background included — over 150ms, so a click landed
      // its state change in ~45ms and then took another 150ms to *look* selected. That reads as
      // lag. 75ms is enough to stop the hover border snapping, and short enough that selection
      // feels immediate.
      className={`min-w-[168px] rounded-[12px] border px-3 py-2 shadow-[0_8px_24px_-12px_rgba(0,0,0,0.6)] transition-colors duration-75 ${stateClass}`}
    >
      <div className="flex items-center gap-2">
        <Icon
          className={`h-3.5 w-3.5 shrink-0 ${status === "active" ? "animate-pulse" : ""}`}
        />
        <span className="text-sm font-medium">{title}</span>
      </div>
      {children ? (
        <div className="mt-1 truncate text-xs text-muted-foreground">{children}</div>
      ) : null}
    </div>
  );
}

export function InputNodeView({ data, selected }: NodeProps) {
  return (
    <>
      <Shell
        title="Input"
        type="input"
        selected={selected}
        status={statusOf(data)}
        testid="node-input"
      >
        chat entry
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function AgentNodeView({ data, selected }: NodeProps) {
  const config = (data as NodeData).config;
  // A role-specialized agent (e.g. "Orchestrator") shows its label; a bare agent shows "Agent".
  const title = String(config.label || "Agent");
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title={title} type="agent" selected={selected} status={statusOf(data)} testid="node-agent">
        {String(config.agent_type ?? "model_based")} · {String(config.model ?? "fake")}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function OutputNodeView({ data, selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Output"
        type="output"
        selected={selected}
        status={statusOf(data)}
        testid="node-output"
      >
        response
      </Shell>
    </>
  );
}

export function CodeNodeView({ data, selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Custom Code"
        type="code"
        selected={selected}
        status={statusOf(data)}
        testid="node-code"
      >
        python · no ceiling
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function RouterNodeView({ data, selected }: NodeProps) {
  // One named source handle per branch (+ the default), spread down the Right edge — wire each
  // to its target; the edge label becomes the branch `condition` in the GraphSpec.
  const config = (data as NodeData).config;
  const names = routerHandleNames(config);
  const isLlm = String(config.kind ?? "rules") === "llm";
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Router" type="router" selected={selected} status={statusOf(data)} testid="node-router">
        {(isLlm ? ["llm", ...names] : names).join(" · ")}
      </Shell>
      {names.map((name, i) => (
        <Handle
          key={name}
          id={name}
          type="source"
          position={Position.Right}
          style={{
            ...handleStyle,
            top: `${((i + 1) / (names.length + 1)) * 100}%`,
          }}
        />
      ))}
    </>
  );
}

export function EvaluatorNodeView({ data, selected }: NodeProps) {
  const max = (data as NodeData).config.scale_max ?? 10;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Evaluator"
        type="evaluator"
        selected={selected}
        status={statusOf(data)}
        testid="node-evaluator"
      >
        LLM judge · 1–{String(max)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function MemoryNodeView({ data, selected }: NodeProps) {
  const op = (data as NodeData).config.operation ?? "buffer";
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Memory" type="memory" selected={selected} status={statusOf(data)} testid="node-memory">
        {String(op)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function ToolNodeView({ data, selected }: NodeProps) {
  const config = (data as NodeData).config;
  const provider = config.provider ?? "demo_search";
  const connectors = useConnectors();
  // For MCP, show where the tools come from next to the provider tag. A connector-backed node
  // has no `mcp_url` on the client — the ref is all the canvas stores, and the server resolves
  // it to a URL at run time — so name the connector instead of reading a URL that is never
  // there. "(no server)" is reserved for a node that genuinely has neither.
  let label = String(provider);
  if (provider === "mcp") {
    const ref = String(config.mcp_connector_ref ?? "");
    const url = String(config.mcp_url ?? "");
    let host = "";
    try {
      host = url ? new URL(url).host : "";
    } catch {
      host = url;
    }
    if (ref) {
      // Until the list loads, say we have *a* connector rather than flashing "(no server)".
      const name = connectors.find((c) => c.id === ref)?.name;
      label = `mcp · ${name ?? "connector"}`;
    } else {
      label = host ? `mcp · ${host}` : "mcp · (no server)";
    }
  }
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Tools" type="tool" selected={selected} status={statusOf(data)} testid="node-tool">
        {label}
      </Shell>
      {/* Loops back to the agent that called it (the ReAct cycle). */}
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function RetrieverNodeView({ data, selected }: NodeProps) {
  const source = (data as NodeData).config.source ?? "demo";
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Knowledge"
        type="retriever"
        selected={selected}
        status={statusOf(data)}
        testid="node-retriever"
      >
        RAG · {String(source)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function ResponderNodeView({ data, selected }: NodeProps) {
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Responder"
        type="responder"
        selected={selected}
        status={statusOf(data)}
        testid="node-responder"
      >
        draft + self-critique
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function RevisorNodeView({ data, selected }: NodeProps) {
  // Branches: "revise" (loop) and "done" (finish), spread down the Right edge — labelled edges
  // carry the names.
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Revisor"
        type="revisor"
        selected={selected}
        status={statusOf(data)}
        testid="node-revisor"
      >
        revise · loop
      </Shell>
      <Handle
        id="revise"
        type="source"
        position={Position.Right}
        style={{ ...handleStyle, top: "33%" }}
      />
      <Handle
        id="done"
        type="source"
        position={Position.Right}
        style={{ ...handleStyle, top: "67%" }}
      />
    </>
  );
}

/** The picture an Image block produced, shown in place after a run.
 *
 *  The lightest of the three previews: a plain `<img>`, no dialog of its own — clicking it opens
 *  the shared `MediaViewer`, the same window the chat and the Media rail use. `nodrag` keeps the
 *  click from being read as the start of a canvas drag.
 */
function ImagePreview({ src }: { src: string }) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);

  async function download() {
    if (saving) return;
    setSaving(true);
    try {
      await downloadUrl(src, filenameFrom("image", "png"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="nodrag relative mt-2 w-56 overflow-hidden rounded" data-testid="node-image-preview">
      {/* Not `next/image`: these are arbitrary blob URLs, which the optimizer would need
          `remotePatterns` for — the same call `ChatImage` and the Media grid already made. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="Generated image"
        onClick={() => setExpanded(true)}
        className="w-full cursor-zoom-in rounded object-cover"
      />
      {/* Always visible rather than hover-revealed — see `MeshPreview` for why. */}
      <div className="absolute top-1 right-1 flex gap-1">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          data-testid="node-image-expand"
          aria-label="View image full size"
          className="rounded bg-background/80 p-1 text-muted-foreground shadow-sm transition hover:text-foreground"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={download}
          disabled={saving}
          data-testid="node-image-download"
          aria-label="Download image"
          className="rounded bg-background/80 p-1 text-muted-foreground shadow-sm transition hover:text-foreground disabled:opacity-50"
        >
          <Download className="h-3.5 w-3.5" />
        </button>
      </div>
      <MediaViewer
        open={expanded}
        onOpenChange={setExpanded}
        kind="image"
        src={src}
        caption="Generated image"
      />
    </div>
  );
}

export function ImageNodeView({ data, selected }: NodeProps) {
  const { config, imageUrl } = data as NodeData;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Image" type="image" selected={selected} status={statusOf(data)} testid="node-image">
        {String(config.model ?? "gpt-image-2")} · {String(config.size ?? "1024x1024")}
        {imageUrl ? <ImagePreview src={imageUrl} /> : null}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function TTSNodeView({ data, selected }: NodeProps) {
  const config = (data as NodeData).config;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Voice" type="tts" selected={selected} status={statusOf(data)} testid="node-tts">
        {String(config.model ?? "gpt-4o-mini-tts")} · {String(config.voice ?? "alloy")}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

// Only ever mounted by a 3D block that has actually produced a mesh, so three.js stays out of
// the canvas bundle for everyone else — see `ModelViewer` for the rest of that argument.
const ModelViewer = dynamic(() => import("@/components/ModelViewer"), {
  ssr: false,
  loading: () => <div className="h-32 w-full animate-pulse rounded bg-white/5" />,
});

/** The orbitable preview a 3D block shows after a run, with expand and save in the corner.
 *
 *  The controls sit *over* the model rather than under it because the node is already the
 *  smallest card on the canvas — a row of buttons beneath would cost as much height as it gives.
 *  They fade in on hover so a resting canvas stays quiet, and stay visible on focus so they are
 *  reachable from the keyboard.
 */
function MeshPreview({ src }: { src: string }) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);

  async function download() {
    if (saving) return;
    setSaving(true);
    try {
      await downloadUrl(src, filenameFrom("model", "glb"));
    } finally {
      setSaving(false);
    }
  }

  return (
    // `nodrag` and `nowheel` are what make this usable: without them React Flow treats an orbit as
    // dragging the block across the canvas, and a zoom gesture as zooming the whole graph. They
    // hand those gestures to the viewer while the rest of the card still drags normally — which is
    // why the viewer is a bounded region *inside* the node rather than the node itself.
    <div
      className="nodrag nowheel relative mt-2 h-48 w-56 overflow-hidden rounded"
      data-testid="node-mesh-preview"
    >
      <ModelViewer src={src} alt="Generated 3D model" className="h-48 w-full" />
      {/* Always visible, not hover-revealed. Two reasons: a hover-only control is unreachable on
          touch and undiscoverable until you happen to point at the right corner of a small card,
          and the `group-hover:` variant this originally used was never emitted into the
          stylesheet — so it silently did nothing. Two small glyphs on a translucent chip are
          quiet enough to leave up. */}
      <div className="absolute top-1 right-1 flex gap-1">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          data-testid="node-mesh-expand"
          aria-label="View 3D model full size"
          className="rounded bg-background/80 p-1 text-muted-foreground shadow-sm transition hover:text-foreground"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={download}
          disabled={saving}
          data-testid="node-mesh-download"
          aria-label="Download 3D model"
          className="rounded bg-background/80 p-1 text-muted-foreground shadow-sm transition hover:text-foreground disabled:opacity-50"
        >
          <Download className="h-3.5 w-3.5" />
        </button>
      </div>
      <MediaViewer
        open={expanded}
        onOpenChange={setExpanded}
        kind="3d"
        src={src}
        caption="Generated 3D model"
      />
    </div>
  );
}

export function MeshNodeView({ data, selected }: NodeProps) {
  const { config, meshUrl } = data as NodeData;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="3D" type="mesh" selected={selected} status={statusOf(data)} testid="node-mesh">
        {String(config.model ?? "fal-ai/trellis")} · image → glb
        {meshUrl ? <MeshPreview src={meshUrl} /> : null}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

/** The clip a Video block produced, playing in place.
 *
 *  A plain `<video>`, unlike its 3D sibling: there is no WebGL context to budget and no heavy
 *  chunk to defer, so the element can simply be here. `nodrag`/`nowheel` still matter — without
 *  them React Flow reads a scrub of the timeline as dragging the block across the canvas.
 *
 *  Muted and unautoplayed on purpose. Several of these can end up on one canvas, and a graph that
 *  starts talking the moment a run finishes is not a graph anyone leaves open.
 */
function VideoPreview({ src }: { src: string }) {
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);

  async function download() {
    if (saving) return;
    setSaving(true);
    try {
      await downloadUrl(src, filenameFrom("video", "mp4"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="nodrag nowheel relative mt-2 w-56 overflow-hidden rounded"
      data-testid="node-video-preview"
    >
      <video
        src={src}
        controls
        muted
        playsInline
        preload="metadata"
        className="h-auto w-full rounded"
      />
      {/* Always visible rather than hover-revealed — see `MeshPreview` for why: `group-hover:`
          emits no rule in this stylesheet, and a hover-only control is unreachable on touch. */}
      <div className="absolute top-1 right-1 flex gap-1">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          data-testid="node-video-expand"
          aria-label="View video full size"
          className="rounded bg-background/80 p-1 text-muted-foreground shadow-sm transition hover:text-foreground"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
        <button
          type="button"
          onClick={download}
          disabled={saving}
          data-testid="node-video-download"
          aria-label="Download video"
          className="rounded bg-background/80 p-1 text-muted-foreground shadow-sm transition hover:text-foreground disabled:opacity-50"
        >
          <Download className="h-3.5 w-3.5" />
        </button>
      </div>
      <MediaViewer
        open={expanded}
        onOpenChange={setExpanded}
        kind="video"
        src={src}
        caption="Generated video"
      />
    </div>
  );
}

export function VideoNodeView({ data, selected }: NodeProps) {
  const { config, videoUrl } = data as NodeData;
  const model = String(config.model ?? "");
  // The endpoint id is long and its only readable part is the tail, which happens to be exactly
  // the fact worth showing: whether this block takes a picture or a prompt.
  const direction = isImageToVideo(model) ? "image → video" : "text → video";
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell
        title="Video"
        type="video"
        selected={selected}
        status={statusOf(data)}
        testid="node-video"
      >
        {direction} · {String(config.duration ?? "5")}s {String(config.resolution ?? "720p")}
        {videoUrl ? <VideoPreview src={videoUrl} /> : null}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

export function UploadNodeView({ data, selected }: NodeProps) {
  const max = (data as NodeData).config.max_images ?? 4;
  return (
    <>
      <Handle type="target" position={Position.Left} style={handleStyle} />
      <Shell title="Upload" type="upload" selected={selected} status={statusOf(data)} testid="node-upload">
        image in · up to {String(max)}
      </Shell>
      <Handle type="source" position={Position.Right} style={handleStyle} />
    </>
  );
}

/**
 * Which component draws each block on the canvas.
 *
 * The `Record<CalyprNodeType, …>` annotation is load-bearing, not decoration. Without it this was
 * an untyped object literal, so a node type registered everywhere else — palette, config panel,
 * codegen, the API — but missing here rendered as an **empty card**: React Flow found no component
 * and drew the two connection handles with nothing between them. Nothing failed; the block was
 * simply invisible. Typed, a missing entry is a build error.
 */
export const nodeTypes: Record<CalyprNodeType, ComponentType<NodeProps>> = {
  input: InputNodeView,
  agent: AgentNodeView,
  output: OutputNodeView,
  code: CodeNodeView,
  router: RouterNodeView,
  evaluator: EvaluatorNodeView,
  memory: MemoryNodeView,
  tool: ToolNodeView,
  responder: ResponderNodeView,
  revisor: RevisorNodeView,
  retriever: RetrieverNodeView,
  image: ImageNodeView,
  mesh: MeshNodeView,
  video: VideoNodeView,
  tts: TTSNodeView,
  upload: UploadNodeView,
};
