"use client";

import { Lock } from "lucide-react";
import { useState } from "react";

import { InfoTip, InfoTipGroup } from "@/components/canvas/InfoTip";
import { NODE_STYLE, PALETTE_ORDER } from "@/components/canvas/node-style";
import { UpgradeDialog } from "@/components/dashboard/UpgradeDialog";
import { type CalyprNodeType, NODE_LABELS } from "@/lib/graph";
import { mediaNodesEnabled } from "@/lib/flags";

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

/** Blocks a plan can withhold. Mirrors `entitlements.PLUS_NODE_TYPES` on the API. */
const PAID_TYPES = new Set<CalyprNodeType>(["mesh"]);

export function Palette({ onAdd, plan }: { onAdd: (type: CalyprNodeType) => void; plan?: string }) {
  // Which paid block was reached for, so the paywall can name it. `null` closes the dialog.
  const [blocked, setBlocked] = useState<CalyprNodeType | null>(null);
  const entitled = mediaNodesEnabled(plan);

  return (
    <InfoTipGroup>
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-2">
          {PALETTE_ORDER.map((type) => {
            const { icon: Icon, description } = NODE_STYLE[type];
            const label = NODE_LABELS[type];
            // Locked, not hidden. A block nobody can discover sells nothing, and hiding it would
            // make the palette silently different per plan — so someone reading a shared graph or
            // a template would meet a block that doesn't exist in their sidebar.
            const locked = PAID_TYPES.has(type) && !entitled;
            return (
              <InfoTip
                key={type}
                title={locked ? `${label} · Plus` : label}
                description={description}
                // `data-testid` belongs on the button itself: ~30 e2e tests click through
                // `helpers.ts`'s `getByTestId('add-' + kind)`. `InfoTip` spreads these onto its
                // `Tooltip.Trigger`, which *is* the button — nothing wraps it.
                data-testid={`add-${type}`}
                data-locked={locked ? "true" : undefined}
                aria-label={locked ? `${label} (requires Plus)` : label}
                onClick={() => (locked ? setBlocked(type) : onAdd(type))}
                // Drag to place, click to append — but a locked tile does neither: dropping one on
                // the canvas would build a graph that only fails at Run.
                draggable={!locked}
                onDragStart={(e) => {
                  if (locked) {
                    e.preventDefault();
                    return;
                  }
                  e.dataTransfer.setData(PALETTE_DND_TYPE, type);
                  e.dataTransfer.effectAllowed = "copy";
                }}
                className={`${TILE_CLASS} ${
                  locked
                    ? "relative cursor-pointer opacity-60 hover:opacity-100"
                    : "cursor-grab active:cursor-grabbing"
                }`}
              >
                {locked ? (
                  <Lock
                    className="absolute top-1.5 right-1.5 h-3 w-3 text-white/50"
                    aria-hidden="true"
                  />
                ) : null}
                <Icon className="h-5 w-5" />
                <span className="text-xs leading-tight font-medium">{label}</span>
              </InfoTip>
            );
          })}
        </div>
      </div>

      <UpgradeDialog
        open={blocked !== null}
        onOpenChange={(open) => !open && setBlocked(null)}
        title={`The ${blocked ? NODE_LABELS[blocked] : ""} block is part of Plus`}
        body="It generates real files through a paid provider, billed per output rather than per token — so it isn't part of the free grant. Upgrade to add it to a canvas."
        event="paid_block_upgrade_clicked"
      />
    </InfoTipGroup>
  );
}
