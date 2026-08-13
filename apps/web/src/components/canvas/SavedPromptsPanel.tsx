"use client";

import { Bookmark } from "lucide-react";

/**
 * Saved prompts — a place to keep the prompts you reuse and copy them back out.
 *
 * Not built yet. It ships as a rail tab first because the tab is the part that has to be agreed:
 * where it sits, what it's called, and that it is a peer of Blocks and Templates rather than
 * something buried in the assistant. The panel says so plainly instead of showing a disabled
 * mock-up of a feature that doesn't exist — an empty list with a dead "New prompt" button reads
 * as broken, where this reads as coming.
 */
export function SavedPromptsPanel() {
  return (
    <div
      className="flex h-full flex-col items-center justify-center px-2 text-center"
      data-testid="prompts-panel"
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
        <Bookmark className="h-5 w-5" />
      </div>
      <p className="mt-3 text-sm font-medium">Saved prompts</p>
      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
        Keep the prompts you reuse here, and copy them straight into an Agent or the assistant.
      </p>
      <span className="mt-3 rounded-full border border-white/15 px-2.5 py-1 text-[11px] text-muted-foreground">
        Coming soon
      </span>
    </div>
  );
}
