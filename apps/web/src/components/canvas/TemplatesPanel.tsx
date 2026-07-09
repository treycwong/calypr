"use client";

import { Background, ReactFlow, ReactFlowProvider } from "@xyflow/react";
import { useState } from "react";

import { nodeTypes } from "@/components/canvas/nodes";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { track } from "@/lib/analytics";
import type { Template } from "@/lib/api";
import { graphToCanvas } from "@/lib/graph";

// A non-interactive mini-map of a template's graph, laid out exactly as it lands on the canvas.
function TemplateDiagram({ template }: { template: Template }) {
  const { nodes, edges } = graphToCanvas(template.graph);
  return (
    <div className="h-56 w-full overflow-hidden rounded-md border border-border bg-card">
      <ReactFlowProvider>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnDrag={false}
          zoomOnScroll={false}
          zoomOnPinch={false}
          zoomOnDoubleClick={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={22} size={1} color="#2c2c33" />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}

// The Templates sidebar panel (the icon-rail "Templates" tab): frameworks + use-case templates.
// Clicking one opens a preview modal (diagram + description); Apply replaces the canvas nodes.
export function TemplatesPanel({
  templates,
  onLoad,
}: {
  templates: Template[];
  onLoad: (id: string) => void;
}) {
  const [preview, setPreview] = useState<Template | null>(null);
  const groups: [string, Template[]][] = [
    ["Frameworks", templates.filter((t) => t.kind === "framework")],
    ["Templates", templates.filter((t) => t.kind === "template")],
  ];

  function apply() {
    if (!preview) return;
    track("template_selected", {
      id: preview.id,
      name: preview.name,
      kind: preview.kind,
    });
    onLoad(preview.id);
    setPreview(null);
  }

  return (
    <div className="flex flex-col gap-3" data-testid="templates-panel">
      <div className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Templates
      </div>
      {templates.length === 0 ? (
        <p className="text-xs text-muted-foreground">Loading…</p>
      ) : null}
      {groups.map(([label, list]) =>
        list.length ? (
          <div key={label} className="space-y-1">
            <div className="text-[11px] font-medium text-muted-foreground">{label}</div>
            {list.map((t) => (
              <button
                key={t.id}
                type="button"
                aria-label={t.name}
                title={t.description}
                onClick={() => setPreview(t)}
                className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-left text-xs font-medium transition hover:border-foreground/20 hover:bg-muted/50"
              >
                {t.name}
              </button>
            ))}
          </div>
        ) : null,
      )}

      <Dialog open={!!preview} onOpenChange={(open) => !open && setPreview(null)}>
        <DialogContent className="sm:max-w-xl" data-testid="template-modal">
          {preview ? (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {preview.name}
                  <span className="rounded-full border border-border px-2 py-0.5 text-[10px] font-normal text-muted-foreground capitalize">
                    {preview.kind}
                  </span>
                </DialogTitle>
                <DialogDescription>{preview.description}</DialogDescription>
              </DialogHeader>
              <TemplateDiagram template={preview} />
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() => setPreview(null)}
                  data-testid="template-cancel"
                >
                  Cancel
                </Button>
                <Button onClick={apply} data-testid="template-apply">
                  Apply
                </Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
