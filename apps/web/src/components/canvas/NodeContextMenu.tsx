"use client";

import { Menu as MenuPrimitive } from "@base-ui/react/menu";
import { Copy, CopyPlus, ClipboardPaste, Settings2, Trash2 } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Right-click menu for a block on the canvas.
 *
 * **Anchored to the cursor, not to a trigger.** React Flow owns each node's DOM wrapper, so
 * wrapping every card in a `ContextMenu.Trigger` would mean threading the node id through `Shell`
 * and all sixteen node views — the shape that has bitten this codebase before. Instead React Flow's
 * own `onNodeContextMenu` reports which node was clicked and where, and Base UI positions this
 * against a virtual element at that point. One menu for the whole canvas, and `nodes.tsx` doesn't
 * change at all.
 *
 * Everything here is also a keyboard shortcut. The menu is the discoverable half: shortcuts you
 * have to already know about are not a feature most people ever find.
 */

/** What the menu is about to act on. A right-click inside a multi-selection acts on the whole
 *  selection; a right-click on an unselected block acts on that block alone (and selects it), which
 *  is what every canvas tool does and what stops an invisible selection being deleted. */
export type ContextTarget = {
  nodeId: string;
  /** Screen coordinates of the click, for the virtual anchor. */
  x: number;
  y: number;
  /** How many blocks the action will touch — used only to label the items honestly. */
  count: number;
  /** Whether the clipboard holds settings this block could accept (same type). */
  canPasteSettings: boolean;
};

const ITEM_CLASS =
  "group/item relative flex cursor-default items-center gap-2 rounded-md px-2 py-1.5 text-sm " +
  "outline-hidden select-none focus:bg-accent focus:text-accent-foreground " +
  "data-disabled:pointer-events-none data-disabled:opacity-50 " +
  "[&_svg]:pointer-events-none [&_svg]:size-3.5 [&_svg]:shrink-0";

function Shortcut({ children }: { children: React.ReactNode }) {
  return (
    <span className="ml-auto pl-4 text-xs tracking-widest text-muted-foreground group-focus/item:text-accent-foreground">
      {children}
    </span>
  );
}

export function NodeContextMenu({
  target,
  onClose,
  onDuplicate,
  onCopy,
  onCopySettings,
  onPasteSettings,
  onDelete,
}: {
  target: ContextTarget | null;
  onClose: () => void;
  onDuplicate: () => void;
  onCopy: () => void;
  onCopySettings: () => void;
  onPasteSettings: () => void;
  onDelete: () => void;
}) {
  const count = target?.count ?? 1;
  const many = count > 1 ? ` ${count} blocks` : "";
  return (
    <MenuPrimitive.Root
      open={!!target}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <MenuPrimitive.Portal>
        <MenuPrimitive.Positioner
          className="isolate z-50 outline-none"
          side="bottom"
          align="start"
          sideOffset={2}
          // A zero-size rectangle at the pointer. `positionMethod: fixed` because the coordinates
          // are viewport-relative and the canvas scrolls and transforms underneath.
          positionMethod="fixed"
          anchor={
            target
              ? {
                  getBoundingClientRect: () =>
                    new DOMRect(target.x, target.y, 0, 0),
                }
              : null
          }
        >
          <MenuPrimitive.Popup
            data-testid="node-context-menu"
            className={cn(
              "z-50 min-w-48 origin-(--transform-origin) rounded-lg bg-popover p-1 text-popover-foreground",
              "shadow-md ring-1 ring-foreground/10 duration-100 outline-none",
              "data-open:animate-in data-open:fade-in-0 data-open:zoom-in-95",
              "data-closed:animate-out data-closed:fade-out-0 data-closed:zoom-out-95",
            )}
          >
            <MenuPrimitive.Item
              className={ITEM_CLASS}
              data-testid="ctx-duplicate"
              onClick={onDuplicate}
            >
              <CopyPlus /> Duplicate{many}
              <Shortcut>⌘D</Shortcut>
            </MenuPrimitive.Item>
            <MenuPrimitive.Item className={ITEM_CLASS} data-testid="ctx-copy" onClick={onCopy}>
              <Copy /> Copy{many}
              <Shortcut>⌘C</Shortcut>
            </MenuPrimitive.Item>

            <MenuPrimitive.Separator className="-mx-1 my-1 h-px bg-border" />

            {/* Settings travel on their own, so one configured block can set up the others without
                replacing them or their wiring. Always the right-clicked block, even inside a
                multi-selection — "copy settings" from several blocks has no single answer. */}
            <MenuPrimitive.Item
              className={ITEM_CLASS}
              data-testid="ctx-copy-settings"
              onClick={onCopySettings}
            >
              <Settings2 /> Copy settings
            </MenuPrimitive.Item>
            <MenuPrimitive.Item
              className={ITEM_CLASS}
              data-testid="ctx-paste-settings"
              // Disabled rather than hidden when there is nothing to paste, or when the copied
              // settings belong to another kind of block: a menu whose items move around between
              // right-clicks is a menu you have to read every time.
              disabled={!target?.canPasteSettings}
              onClick={onPasteSettings}
            >
              <ClipboardPaste /> Paste settings
            </MenuPrimitive.Item>

            <MenuPrimitive.Separator className="-mx-1 my-1 h-px bg-border" />

            <MenuPrimitive.Item
              className={cn(ITEM_CLASS, "text-destructive focus:bg-destructive/10 focus:text-destructive")}
              data-testid="ctx-delete"
              onClick={onDelete}
            >
              <Trash2 /> Delete{many}
              <Shortcut>⌫</Shortcut>
            </MenuPrimitive.Item>
          </MenuPrimitive.Popup>
        </MenuPrimitive.Positioner>
      </MenuPrimitive.Portal>
    </MenuPrimitive.Root>
  );
}
