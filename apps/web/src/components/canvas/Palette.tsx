"use client";

import { Button } from "@/components/ui/button";
import type { CalyprNodeType } from "@/lib/graph";

const ITEMS: { type: CalyprNodeType; label: string; hint: string }[] = [
  { type: "input", label: "Input", hint: "entry" },
  { type: "upload", label: "Upload", hint: "image in" },
  { type: "agent", label: "Agent", hint: "LLM" },
  { type: "tool", label: "Tools", hint: "search" },
  { type: "retriever", label: "Knowledge", hint: "RAG" },
  { type: "image", label: "Image", hint: "gpt-image" },
  { type: "tts", label: "Voice", hint: "text→speech" },
  { type: "responder", label: "Responder", hint: "draft" },
  { type: "revisor", label: "Revisor", hint: "revise" },
  { type: "router", label: "Router", hint: "route" },
  { type: "evaluator", label: "Evaluator", hint: "score" },
  { type: "memory", label: "Memory", hint: "recall" },
  { type: "code", label: "Custom Code", hint: "Python" },
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
