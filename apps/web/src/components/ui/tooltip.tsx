"use client";

import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";
import type { ReactNode } from "react";

/**
 * A compact, one-line tooltip for a control whose meaning isn't carried by its own label —
 * icon-only buttons, mostly.
 *
 * Not a duplicate of `components/canvas/InfoTip`, which is the same Base UI primitive dressed as
 * a `w-64` card with a bold title and a paragraph: that one *teaches* a block you don't know yet.
 * This one *names* a control you can already see. Same library, deliberately different shapes.
 *
 * `TooltipPrimitive.Trigger` renders a real `<button>` and forwards every button prop, so the
 * trigger **is** the control — `onClick`, `className` and `data-testid` all land on the element a
 * click has to hit, with nothing wrapped around it.
 *
 * **Do not pass `disabled`.** Browsers suppress pointer events on a disabled button, so the
 * tooltip would go silent in exactly the case where the explanation matters most — a control that
 * is off and doesn't say why. Use `aria-disabled` and make the handler a no-op instead; callers
 * are responsible for the visual dimming.
 */
export function Tooltip({
  label,
  side = "top",
  children,
  ...button
}: {
  label: string;
  side?: "top" | "right" | "bottom" | "left";
  children: ReactNode;
} & React.ComponentProps<"button">) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger {...button}>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Positioner side={side} sideOffset={6} collisionPadding={8}>
          <TooltipPrimitive.Popup className="z-50 max-w-56 rounded-md bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md ring-1 ring-foreground/10 duration-100 data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95 data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95">
            {label}
          </TooltipPrimitive.Popup>
        </TooltipPrimitive.Positioner>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

/**
 * Shared open/close timing for a group of `Tooltip`s — moving between neighbouring controls swaps
 * the tooltip instantly rather than waiting out the delay again. Renders no DOM.
 */
export function TooltipGroup({
  children,
  delay = 300,
}: {
  children: ReactNode;
  delay?: number;
}) {
  return <TooltipPrimitive.Provider delay={delay}>{children}</TooltipPrimitive.Provider>;
}
