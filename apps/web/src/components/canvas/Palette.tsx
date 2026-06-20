"use client";

import { Button } from "@/components/ui/button";
import type { CalyprNodeType } from "@/lib/graph";

const ITEMS: { type: CalyprNodeType; label: string; hint: string }[] = [
  { type: "input", label: "Input", hint: "entry" },
  { type: "agent", label: "Agent", hint: "LLM" },
  { type: "output", label: "Output", hint: "reply" },
];

export function Palette({ onAdd }: { onAdd: (type: CalyprNodeType) => void }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Blocks
      </div>
      {ITEMS.map((it) => (
        <Button
          key={it.type}
          variant="outline"
          className="justify-start"
          onClick={() => onAdd(it.type)}
          data-testid={`add-${it.type}`}
        >
          + {it.label}
          <span className="ml-auto text-xs text-muted-foreground">{it.hint}</span>
        </Button>
      ))}
      <p className="mt-1 text-xs text-muted-foreground">
        Adding a block links it after the previous one.
      </p>
    </div>
  );
}
