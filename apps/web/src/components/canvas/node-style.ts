import {
  AudioLines,
  Bot,
  Box,
  Brain,
  Code2,
  Gauge,
  // Collides with the DOM `Image` global, so it is aliased everywhere it's used.
  Image as ImageIcon,
  Library,
  type LucideIcon,
  MessageSquareReply,
  MessageSquareText,
  PenLine,
  RefreshCw,
  Split,
  Upload,
  Workflow,
  Wrench,
} from "lucide-react";

import type { CalyprNodeType } from "@/lib/graph";

/**
 * How each block looks and reads, everywhere it appears.
 *
 * Deliberately **not** in `lib/graph.ts`: that module is the canvas↔DSL contract and gets pulled
 * into code paths that never render anything, so importing lucide there would drag icon
 * components into every bundle that merely touches a GraphSpec. Icons are a UI concern and live
 * beside the components that draw them.
 *
 * The Palette tiles and the canvas node cards both read this, so the two can't drift apart — the
 * block you pick from the sidebar is visibly the block that lands on the canvas.
 *
 * The icons carry no colour on purpose — they inherit `currentColor`, so a tile and a node card
 * are styled entirely by their container. `edge` is the one exception: it tints the *wire leaving*
 * this block, which is where colour still earns its place. A wire is a thin line with no label,
 * so on a graph of any size the only way to see what feeds what is by hue. These are the Tailwind
 * `-500`s: they started as `-300` pastels, which were too washed out to trace across a busy
 * canvas. They are also the only colour left on the canvas apart from run state, which stays cyan
 * (running) and emerald (done) and overrides the wire tint while a run is in flight — so no wire
 * may be cyan, or a static graph would read as mid-run.
 *
 * `description` is what the hover info box shows; it is the only place a block explains itself,
 * so keep these written for someone who has never seen the block before.
 */
export const NODE_STYLE: Record<
  CalyprNodeType,
  { icon: LucideIcon; description: string; edge: string }
> = {
  input: {
    icon: MessageSquareText,
    edge: "#0ea5e9",
    description: "Where the conversation starts — the user's message enters the graph here.",
  },
  upload: {
    icon: Upload,
    edge: "#f97316",
    description: "Accepts images from the user, so later blocks can look at them.",
  },
  agent: {
    icon: Bot,
    edge: "#8b5cf6",
    description:
      "An LLM step. Give it a system prompt and it reasons over the conversation so far.",
  },
  tool: {
    icon: Wrench,
    edge: "#eab308",
    description:
      "Lets an agent call out to the world — web search, or any MCP server you've connected.",
  },
  retriever: {
    icon: Library,
    edge: "#84cc16",
    description:
      "Retrieval-augmented generation. Pulls matching passages from a knowledge source before the agent answers.",
  },
  image: {
    icon: ImageIcon,
    edge: "#ec4899",
    description: "Generates an image from a text prompt.",
  },
  mesh: {
    icon: Box,
    // Not orange, though it would suit: `upload` already owns #f97316, and Upload → 3D is the
    // canonical wiring for this block — two orange wires in the one graph that most needs them
    // told apart. The wheel is genuinely full at fifteen once cyan is reserved for run state, so
    // this is red-600 against the router's rose-500; the two rarely sit adjacent.
    edge: "#dc2626",
    description: "Turns an image into a downloadable 3D model. Plus only.",
  },
  tts: {
    icon: AudioLines,
    edge: "#a855f7",
    description: "Turns text into spoken audio, in the voice you pick.",
  },
  responder: {
    icon: PenLine,
    edge: "#6366f1",
    description: "Drafts an answer and critiques its own draft in a single step.",
  },
  revisor: {
    icon: RefreshCw,
    edge: "#d946ef",
    description: "Improves a draft, looping until it is good enough or the limit is reached.",
  },
  router: {
    icon: Split,
    edge: "#f43f5e",
    description: "Sends the run down one of several branches, by rule or by asking a model.",
  },
  evaluator: {
    icon: Gauge,
    edge: "#f59e0b",
    description: "Scores the current answer, so a loop knows when to stop.",
  },
  memory: {
    icon: Brain,
    edge: "#14b8a6",
    description: "Recalls earlier turns, so the agent remembers across the conversation.",
  },
  code: {
    icon: Code2,
    // The one deliberately unsaturated wire. Custom Code is the escape hatch — it isn't one of
    // the built-in capabilities, and a neutral steel line says that at a glance. It also frees a
    // hue: fourteen distinguishable saturated colours is one more than the wheel comfortably
    // gives once cyan is reserved for run state.
    edge: "#94a3b8",
    description: "Your own Python, run as a graph step — the escape hatch when no block fits.",
  },
  output: {
    icon: MessageSquareReply,
    edge: "#10b981",
    description: "Where the run ends. Whatever reaches here is the reply.",
  },
};

/**
 * The order blocks appear in the palette. Authored, not alphabetical — it walks a graph roughly
 * the way you'd build one (entry → model → retrieval → media → refinement → control → exit), so
 * don't sort it.
 */
export const PALETTE_ORDER: CalyprNodeType[] = [
  "input",
  "upload",
  "agent",
  "tool",
  "retriever",
  "image",
  "mesh",
  "tts",
  "responder",
  "revisor",
  "router",
  "evaluator",
  "memory",
  "code",
  "output",
];

/**
 * Most-to-least distinctive node type. A graph made of Input → Agent → Output is every graph;
 * one containing an Image node is *the image one*. Used to pick a template's tile icon.
 */
const CHARACTERISTIC_ORDER: CalyprNodeType[] = [
  "mesh",
  "image",
  "tts",
  "upload",
  "retriever",
  "tool",
  "router",
  "evaluator",
  "revisor",
  "responder",
  "memory",
  "code",
  "agent",
];

/**
 * Pick an icon for a template from the blocks it is made of, rather than maintaining a
 * hand-written icon per template: templates come from the API and are added server-side, so a
 * frontend list would silently fall behind. Falls back to a generic graph glyph for a template
 * built only from Input/Output.
 */
export function iconForNodeTypes(types: string[]): LucideIcon {
  const present = new Set(types);
  const match = CHARACTERISTIC_ORDER.find((t) => present.has(t));
  return match ? NODE_STYLE[match].icon : Workflow;
}
