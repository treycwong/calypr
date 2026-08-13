"use client";

import { useReactFlow, useViewport } from "@xyflow/react";
import {
  ChevronDown,
  Hand,
  type LucideIcon,
  MousePointer2,
  Redo2,
  Undo2,
} from "lucide-react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

/** Which pointer gesture the canvas is in: `select` marquees and drags nodes, `pan` grabs the
 *  canvas. Mirrors the arrow/hand pair every design tool has; the keyboard shortcuts (V/H) live
 *  with the rest of the canvas hotkeys in the page, not here, because they have to share the
 *  "ignore while typing" guard with undo/redo. */
export type CanvasTool = "select" | "pan";

/** Animation for the programmatic zoom steps. Short enough not to feel laggy when you hold ⌘+,
 *  long enough that the jump reads as a move rather than a cut. */
const ZOOM_DURATION = 150;

/** Same shape as the rail's `RailButton`, laid out horizontally: h-9 w-9, muted when idle, filled
 *  when active. Kept local rather than shared — the rail's version is always a toggle, this one
 *  also has to handle `disabled` (undo/redo at the ends of the history stacks). */
function ToolbarButton({
  icon: Icon,
  label,
  active,
  disabled,
  onClick,
  testid,
}: {
  icon: LucideIcon;
  label: string;
  active?: boolean;
  disabled?: boolean;
  onClick: () => void;
  testid: string;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      {...(active === undefined ? {} : { "aria-pressed": active })}
      disabled={disabled}
      data-testid={testid}
      onClick={onClick}
      className={`flex h-9 w-9 items-center justify-center rounded-md transition disabled:pointer-events-none disabled:opacity-40 ${
        active
          ? "bg-muted text-foreground"
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
      }`}
    >
      <Icon className="h-4 w-4" />
    </button>
  );
}

function Divider() {
  return <div className="mx-1 h-5 w-px bg-border" />;
}

/**
 * The floating canvas toolbar: tool switch, history, zoom.
 *
 * Replaces React Flow's stock `<Controls />` and `<MiniMap />`. Zoom is owned here rather than
 * passed in — `useViewport()` re-renders this component on every viewport change, and hoisting
 * that into the page would re-render the whole canvas shell on every pan.
 */
export function CanvasToolbar({
  tool,
  onToolChange,
  canUndo,
  canRedo,
  onUndo,
  onRedo,
}: {
  tool: CanvasTool;
  onToolChange: (tool: CanvasTool) => void;
  canUndo: boolean;
  canRedo: boolean;
  onUndo: () => void;
  onRedo: () => void;
}) {
  const { zoom } = useViewport();
  const { zoomIn, zoomOut } = useReactFlow();

  return (
    <div
      role="toolbar"
      aria-label="Canvas tools"
      data-testid="canvas-toolbar"
      className="flex items-center gap-1 rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-md"
    >
      <ToolbarButton
        icon={MousePointer2}
        label="Select (V)"
        active={tool === "select"}
        onClick={() => onToolChange("select")}
        testid="tool-select"
      />
      <ToolbarButton
        icon={Hand}
        label="Pan (H)"
        active={tool === "pan"}
        onClick={() => onToolChange("pan")}
        testid="tool-pan"
      />

      <Divider />

      <ToolbarButton
        icon={Undo2}
        label="Undo (⌘Z)"
        disabled={!canUndo}
        onClick={onUndo}
        testid="undo"
      />
      <ToolbarButton
        icon={Redo2}
        label="Redo (⌘⇧Z)"
        disabled={!canRedo}
        onClick={onRedo}
        testid="redo"
      />

      <Divider />

      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label="Zoom"
          data-testid="zoom-menu"
          className="flex h-9 items-center gap-1 rounded-md px-2 text-xs tabular-nums text-muted-foreground transition hover:bg-muted/50 hover:text-foreground data-[popup-open]:bg-muted data-[popup-open]:text-foreground"
        >
          <span data-testid="zoom-level">{Math.round(zoom * 100)}%</span>
          <ChevronDown className="h-3 w-3" />
        </DropdownMenuTrigger>
        {/* Anchored above: the toolbar sits on the bottom edge of the canvas. */}
        <DropdownMenuContent side="top" align="end" className="w-auto min-w-40">
          <DropdownMenuItem
            data-testid="zoom-in"
            onClick={() => zoomIn({ duration: ZOOM_DURATION })}
          >
            Zoom in
            <DropdownMenuShortcut>⌘+</DropdownMenuShortcut>
          </DropdownMenuItem>
          <DropdownMenuItem
            data-testid="zoom-out"
            onClick={() => zoomOut({ duration: ZOOM_DURATION })}
          >
            Zoom out
            <DropdownMenuShortcut>⌘−</DropdownMenuShortcut>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
