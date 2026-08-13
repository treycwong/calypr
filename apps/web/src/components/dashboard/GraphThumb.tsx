"use client";

import { NODE_STYLE } from "@/components/canvas/node-style";
import type { GraphPreview } from "@/lib/api";
import { type CalyprNodeType, NODE_LABELS } from "@/lib/graph";

/** Inset (in % of the box) so a node chip at the extreme edge isn't clipped by the card. */
const PAD = 14;

/**
 * A project's graph, at thumbnail size — the blocks as they sit on the canvas, not an abstraction.
 *
 * The nodes are real chips (the block's own icon in a bordered card) rather than dots, so a
 * project on the dashboard is recognisable as the thing you built: a graph with an Image block
 * in it *looks* like one. Wires take the colour of the block they leave, exactly as on the canvas.
 *
 * Not a React Flow instance. The dashboard renders one of these per project, and each
 * `<ReactFlow>` brings a store, a resize observer and a zoom behaviour with it — none of which a
 * static picture needs. Wires are one `<svg>`; the chips are absolutely-positioned elements, so
 * they can use the same lucide components the canvas does.
 */
export function GraphThumb({ preview }: { preview: GraphPreview | null | undefined }) {
  const nodes = preview?.nodes ?? [];
  if (!nodes.length) {
    return (
      <div
        className="flex h-full w-full items-center justify-center"
        data-testid="graph-thumb-empty"
      >
        <span className="text-[11px] text-muted-foreground">Empty canvas</span>
      </div>
    );
  }

  // Fit the saved positions into the box **at a uniform scale**, then centre.
  //
  // Scaling each axis independently to fill the square is the obvious version and it lies: a
  // typical graph is wide and shallow, so stretching Y to fill the height turned a 74px rise
  // across a 500px span into a mountain. A thumbnail is only useful if it is the same shape as
  // the thing it stands for.
  const xs = nodes.map((n) => n.x);
  const ys = nodes.map((n) => n.y);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const spanX = Math.max(...xs) - minX;
  const spanY = Math.max(...ys) - minY;
  const box = 100 - 2 * PAD;
  // A single node, or a perfectly straight line, has no extent on one axis — fall back to a
  // scale that just centres it rather than dividing by zero.
  const scale = Math.min(spanX > 0 ? box / spanX : Infinity, spanY > 0 ? box / spanY : Infinity);
  const k = Number.isFinite(scale) ? scale : 0;
  const at = (n: { x: number; y: number }) => ({
    x: 50 + (n.x - minX - spanX / 2) * k,
    y: 50 + (n.y - minY - spanY / 2) * k,
  });
  const points = nodes.map(at);

  return (
    <div className="relative h-full w-full" data-testid="graph-thumb">
      {/* `preserveAspectRatio="none"` makes the viewBox a straight 0–100 percentage space on both
          axes, so the lines land on the same coordinates the chips are positioned at. */}
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="absolute inset-0 h-full w-full"
        aria-hidden
      >
        {(preview?.edges ?? []).map(([s, t], i) => {
          const a = points[s];
          const b = points[t];
          if (!a || !b) return null;
          const style = NODE_STYLE[nodes[s].type as CalyprNodeType];
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={style?.edge ?? "#71717a"}
              // Non-scaling so a wide card doesn't stretch the stroke into a smear — the
              // viewBox is deliberately distorted, and this opts the stroke out of that.
              vectorEffect="non-scaling-stroke"
              strokeWidth={1.5}
              strokeLinecap="round"
            />
          );
        })}
      </svg>

      {points.map((p, i) => {
        const type = nodes[i].type as CalyprNodeType;
        const style = NODE_STYLE[type];
        const Icon = style?.icon;
        return (
          <div
            key={i}
            title={NODE_LABELS[type] ?? type}
            style={{ left: `${p.x}%`, top: `${p.y}%` }}
            // Sits on top of the wires the way a solid card does on the canvas.
            className="absolute flex h-5 w-7 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-[4px] border border-white/15 bg-neutral-800 shadow-sm"
            data-node-type={type}
          >
            {Icon ? <Icon className="h-3 w-3 text-foreground/80" /> : null}
          </div>
        );
      })}
    </div>
  );
}
