"use client";

import { track } from "@/lib/analytics";
import type { Template } from "@/lib/api";

// The Templates sidebar panel (the icon-rail "Templates" tab): frameworks + use-case templates,
// click one to load it onto the canvas. Replaces the old header dropdown.
export function TemplatesPanel({
  templates,
  onLoad,
}: {
  templates: Template[];
  onLoad: (id: string) => void;
}) {
  const groups: [string, Template[]][] = [
    ["Frameworks", templates.filter((t) => t.kind === "framework")],
    ["Templates", templates.filter((t) => t.kind === "template")],
  ];
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
                onClick={() => {
                  track("template_selected", { id: t.id, name: t.name, kind: t.kind });
                  onLoad(t.id);
                }}
                className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-left text-xs font-medium transition hover:border-foreground/20 hover:bg-muted/50"
              >
                {t.name}
              </button>
            ))}
          </div>
        ) : null,
      )}
    </div>
  );
}
