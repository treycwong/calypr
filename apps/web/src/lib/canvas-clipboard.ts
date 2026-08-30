import type { Edge, Node } from "@xyflow/react";

import type { NodeData } from "@/lib/graph";

/**
 * Copying blocks on the canvas.
 *
 * The pure half of the feature — building a clipboard payload from a selection, and turning a
 * payload back into fresh nodes and edges. The React wiring (the listeners, undo, selection) is in
 * `app/canvas/page.tsx`; everything decided here is decided without touching the DOM.
 *
 * The payload is JSON on the **real system clipboard**, not a variable held in the page. That is
 * what lets you copy a block out of one project and paste it into another, or into a second tab.
 * It works without a permissions prompt because the app rides the browser's own `copy`/`paste`
 * events, where clipboard access is granted synchronously as part of the user's gesture — the
 * async `navigator.clipboard.readText()` is the API that prompts, and it is deliberately not used.
 */

/** Marks a payload as ours. Versioned so a later format change can be told apart from this one
 *  rather than throwing on a stale copy still sitting in someone's clipboard. */
const KIND = "calypr.canvas.clipboard/1";

/** How far a pasted copy lands from the original, in canvas units. Enough that it reads as a
 *  second block rather than a mis-render, and small enough to stay in view. */
const OFFSET = 48;

export type ClipboardPayload = {
  kind: typeof KIND;
  nodes: { id: string; type: string; position: { x: number; y: number }; config: unknown }[];
  edges: { source: string; target: string; label?: string }[];
};

/**
 * Build a payload from the selected nodes, or null when nothing is selected.
 *
 * **Only `config` travels.** A node's `data` also carries run results — its status glow and the
 * image, video or mesh it last produced — and those belong to a run, not to the block. A copy that
 * arrived already displaying the original's output would be claiming to have generated something
 * it never ran.
 *
 * Edges are kept only when *both* ends are in the selection. A copied block cannot keep a wire to
 * a block that wasn't copied: the wire would either dangle or silently re-point at the original,
 * and re-pointing is the worse of the two — it looks connected and feeds the wrong branch.
 */
export function copySelection(nodes: Node<NodeData>[], edges: Edge[]): ClipboardPayload | null {
  const selected = nodes.filter((n) => n.selected);
  if (!selected.length) return null;
  const ids = new Set(selected.map((n) => n.id));
  return {
    kind: KIND,
    nodes: selected.map((n) => ({
      id: n.id,
      type: n.type ?? "",
      position: { x: Math.round(n.position.x), y: Math.round(n.position.y) },
      config: n.data.config,
    })),
    edges: edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({
        source: e.source,
        target: e.target,
        ...(e.label ? { label: String(e.label) } : {}),
      })),
  };
}

/** Parse clipboard text into a payload, or null if it isn't ours.
 *
 *  Deliberately strict: the paste handler runs on every paste the canvas sees, so anything that
 *  isn't a Calypr fragment — a URL, a paragraph, JSON from somewhere else — has to fall through
 *  untouched rather than being coerced into a block. */
export function parsePayload(text: string): ClipboardPayload | null {
  if (!text || !text.includes(KIND)) return null;
  try {
    const parsed = JSON.parse(text) as ClipboardPayload;
    if (parsed?.kind !== KIND || !Array.isArray(parsed.nodes) || !parsed.nodes.length) return null;
    return { ...parsed, edges: Array.isArray(parsed.edges) ? parsed.edges : [] };
  } catch {
    return null;
  }
}

/**
 * Turn a payload into new nodes and edges, ready to add to the canvas.
 *
 * `step` spaces repeated pastes of the same payload so they don't stack into one illegible pile:
 * the first lands one offset away, the second two, and so on.
 *
 * New ids are checked against the ids actually on the canvas rather than taken from a counter.
 * The counter is reseeded to the node count whenever a graph is loaded, so on a graph whose blocks
 * came from a template — `in`, `image`, `out` — it can hand out an id that is already in use, and
 * a duplicate node id is the one thing the whole canvas is keyed on.
 */
export function materialize(
  payload: ClipboardPayload,
  existing: Node<NodeData>[],
  step = 1,
): { nodes: Node<NodeData>[]; edges: Edge[] } {
  const taken = new Set(existing.map((n) => n.id));
  const rename = new Map<string, string>();

  const nodes = payload.nodes.map((n) => {
    let i = 1;
    let id = `${n.type}-${i}`;
    while (taken.has(id)) id = `${n.type}-${++i}`;
    taken.add(id);
    rename.set(n.id, id);
    return {
      id,
      type: n.type,
      position: { x: n.position.x + OFFSET * step, y: n.position.y + OFFSET * step },
      // Selected, so the copy is what you drag next and a second duplicate compounds rather than
      // re-copying the original.
      selected: true,
      data: { config: { ...((n.config as Record<string, unknown>) ?? {}) } },
    } as Node<NodeData>;
  });

  const edges = payload.edges.flatMap((e) => {
    const source = rename.get(e.source);
    const target = rename.get(e.target);
    if (!source || !target) return [];
    return [
      {
        id: `e-${source}-${target}-${Math.random().toString(36).slice(2, 8)}`,
        source,
        target,
        ...(e.label ? { label: e.label } : {}),
      } as Edge,
    ];
  });

  return { nodes, edges };
}

/**
 * A block's settings on their own, so one configured block can set up the others.
 *
 * Held in memory for the session rather than written to the system clipboard, unlike a copied
 * *block*. Two reasons: it is invoked from a menu item rather than a real copy gesture, so the
 * synchronous clipboard access that makes block copy prompt-free isn't available; and reading it
 * back to answer "can this block accept these settings?" every time the menu opens would mean
 * `navigator.clipboard.readText()`, which is the call that prompts. Carrying whole blocks between
 * projects already works through ⌘C/⌘V — this is the in-canvas tool.
 */
export type SettingsClipboard = { type: string; config: Record<string, unknown> };

/** Settings that may be pasted onto `node` — same block type only.
 *
 *  Type-matched because configs are not interchangeable: writing an Image block's config onto a
 *  Video block would set fields it does not have and drop every field it does, leaving a block
 *  that looks configured and cannot run. */
export function settingsFor(
  clip: SettingsClipboard | null,
  node: Node<NodeData> | undefined,
): Record<string, unknown> | null {
  if (!clip || !node || node.type !== clip.type) return null;
  return clip.config;
}
