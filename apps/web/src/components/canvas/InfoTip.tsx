"use client";

import { Tooltip } from "@base-ui/react/tooltip";
import type { ReactNode } from "react";

/**
 * A tile that explains itself on a longer hover.
 *
 * The sidebar tiles are icon + one short label, which is enough to recognise a block you already
 * know and not enough to learn one. Rather than crowd the tile, the full name and a sentence of
 * description appear in a card after a beat — Base UI's default 600ms `delay`, long enough that
 * sweeping the pointer across the grid doesn't flash a dozen cards.
 *
 * `Tooltip.Trigger` renders a real `<button>` and forwards every button prop, so the trigger *is*
 * the tile: `onClick`, `className` and `data-testid` all land on the same element a click has to
 * hit. Nothing is wrapped around it.
 */
export function InfoTip({
  title,
  description,
  children,
  ...button
}: {
  title: string;
  description: string;
  children: ReactNode;
} & React.ComponentProps<"button">) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger {...button}>{children}</Tooltip.Trigger>
      <Tooltip.Portal>
        {/* To the side rather than above: the grid is two columns in a narrow rail, so a card
            over the tile would cover its neighbours. `flip` sends it left for the right column. */}
        <Tooltip.Positioner side="right" align="start" sideOffset={8} collisionPadding={8}>
          <Tooltip.Popup className="z-50 w-64 rounded-lg bg-popover p-3 text-popover-foreground shadow-md ring-1 ring-foreground/10 duration-100 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95">
            <p className="text-sm font-medium">{title}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{description}</p>
          </Tooltip.Popup>
        </Tooltip.Positioner>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

/**
 * Shared open/close timing for a group of `InfoTip`s. Once one card is showing, moving to a
 * neighbouring tile swaps it instantly instead of waiting out the delay again — the behaviour you
 * want when comparing blocks. Wrap a panel in this; it renders no DOM.
 */
export function InfoTipGroup({ children }: { children: ReactNode }) {
  return <Tooltip.Provider delay={600}>{children}</Tooltip.Provider>;
}
