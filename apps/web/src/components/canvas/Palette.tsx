"use client";

import { InfoTip, InfoTipGroup } from "@/components/canvas/InfoTip";
import { NODE_STYLE, PALETTE_ORDER } from "@/components/canvas/node-style";
import { type CalyprNodeType, NODE_LABELS } from "@/lib/graph";

/**
 * The tile every sidebar grid uses — Blocks here, Templates next door.
 *
 * Monochrome on purpose: a white icon on a hairline white border, filling with low-opacity white
 * on hover. Colour on this canvas already means "this node is running" (the cyan run glow), so
 * spending fourteen hues on a static list of blocks made the sidebar the loudest thing on screen
 * and left the running state competing for attention.
 */
export const TILE_CLASS =
  "flex aspect-[4/3] w-full flex-col items-center justify-center gap-2 rounded-lg border border-white/10 bg-white/[0.02] px-2 text-center transition hover:border-white/25 hover:bg-white/[0.07]";

/** The dataTransfer key a dragged block travels under. A custom MIME type rather than
 *  `text/plain`, so the canvas can tell one of our blocks from a dragged file, link or text
 *  selection and ignore the rest. */
export const PALETTE_DND_TYPE = "application/calypr-block";

export function Palette({ onAdd }: { onAdd: (type: CalyprNodeType) => void }) {
  return (
    <InfoTipGroup>
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-2">
          {PALETTE_ORDER.map((type) => {
            const { icon: Icon, description } = NODE_STYLE[type];
            const label = NODE_LABELS[type];
            return (
              <InfoTip
                key={type}
                title={label}
                description={description}
                // `data-testid` belongs on the button itself: ~30 e2e tests click through
                // `helpers.ts`'s `getByTestId('add-' + kind)`. `InfoTip` spreads these onto its
                // `Tooltip.Trigger`, which *is* the button — nothing wraps it.
                data-testid={`add-${type}`}
                aria-label={label}
                onClick={() => onAdd(type)}
                // Drag to place, click to append. The grab cursor is the only thing advertising
                // that the tile is draggable at all, so it is not decoration.
                draggable
                onDragStart={(e) => {
                  e.dataTransfer.setData(PALETTE_DND_TYPE, type);
                  e.dataTransfer.effectAllowed = "copy";
                }}
                className={`${TILE_CLASS} cursor-grab active:cursor-grabbing`}
              >
                <Icon className="h-5 w-5" />
                <span className="text-xs leading-tight font-medium">{label}</span>
              </InfoTip>
            );
          })}
        </div>
      </div>
    </InfoTipGroup>
  );
}
