"use client";

import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

// Scaffold for the in-canvas AI assistant. The chat UI is in place; the model backend is wired
// up in a follow-up (it'll suggest/assemble blocks from a plain-English description).
export function AssistantPanel() {
  return (
    <div className="flex h-full flex-col" data-testid="assistant-panel">
      <div className="flex items-center gap-2 border-b border-border px-3 py-2">
        <Sparkles className="h-4 w-4 text-violet-400" />
        <span className="text-sm font-medium">AI assistant</span>
        <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
          coming soon
        </span>
      </div>
      <div className="flex-1 overflow-auto p-3">
        <div className="rounded-lg border border-border bg-card p-3 text-xs text-muted-foreground">
          Hi! Soon you’ll be able to describe the agent you want here and I’ll suggest — or
          wire up — the right blocks for you. Not connected yet.
        </div>
      </div>
      <div className="border-t border-border p-3">
        <div className="flex items-center gap-2">
          <Input
            placeholder="Ask the assistant…"
            disabled
            data-testid="assistant-input"
          />
          <Button size="sm" disabled>
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}
