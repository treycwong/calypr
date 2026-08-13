"use client";

import { Background, ReactFlow, ReactFlowProvider } from "@xyflow/react";
import { useState } from "react";

import { InfoTip, InfoTipGroup } from "@/components/canvas/InfoTip";
import { iconForNodeTypes } from "@/components/canvas/node-style";
import { nodeTypes } from "@/components/canvas/nodes";
import { TILE_CLASS } from "@/components/canvas/Palette";
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
          <Background gap={22} size={1} color="#4a4a52" />
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
  // "Workflows" rather than "Templates": the panel itself is called Templates, so a group inside
  // it with the same name said nothing about what separates the two. These are complete
  // multi-agent systems for a job ("Market research report"); the others are the architecture
  // patterns an agent can be built on.
  const groups: [string, Template[]][] = [
    ["Frameworks", templates.filter((t) => t.kind === "framework")],
    ["Workflows", templates.filter((t) => t.kind === "template")],
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
    <InfoTipGroup>
      <div className="flex flex-col gap-3" data-testid="templates-panel">
        {templates.length === 0 ? (
          <p className="text-xs text-muted-foreground">Loading…</p>
        ) : null}
        {groups.map(([label, list]) =>
          list.length ? (
            <div key={label} className="space-y-1.5">
              {/* Same treatment as the Connectors panel's "CONNECTED ACCOUNTS" / "MODELS", so a
                  section heading looks like a section heading in every rail panel. */}
              <div className="font-mono text-xs font-medium tracking-wide uppercase text-muted-foreground">
                {label}
              </div>
              <div className="grid grid-cols-2 gap-2">
                {list.map((t) => {
                  const Icon = iconForNodeTypes((t.graph.nodes ?? []).map((n) => n.type));
                  return (
                    <InfoTip
                      key={t.id}
                      title={t.name}
                      description={t.description}
                      // Load-bearing: several specs select these by accessible name, scoped to
                      // `templates-panel` (`getByRole("button", { name, exact: true })`).
                      aria-label={t.name}
                      onClick={() => setPreview(t)}
                      className={TILE_CLASS}
                    >
                      <Icon className="h-5 w-5" />
                      {/* Template names are sentences ("Customer support automation") where block
                        labels are one word, so they clamp rather than blow the tile out of shape.
                        The hover card carries the full name, which is why clamping is safe. */}
                      <span className="line-clamp-2 text-[11px] leading-tight font-medium">
                        {t.name}
                      </span>
                    </InfoTip>
                  );
                })}
              </div>
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
    </InfoTipGroup>
  );
}
