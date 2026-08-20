"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ProjectArt } from "@/components/dashboard/ProjectArt";
import { track } from "@/lib/analytics";
import { createAgent, listTemplates, type Template } from "@/lib/api";

/** The card's artwork. Isolated because it is the one part meant to change: swapping the
 *  generative fields for real photography is a change to this component and nothing else. */
function WorkflowThumb({ template }: { template: Template }) {
  // Seeded by template id — a workflow's art never changes, and no two look alike. Eighteen
  // graphs that are mostly a short line of dots would otherwise be eighteen identical cards.
  return (
    <div className="aspect-[16/10] w-full overflow-hidden">
      <ProjectArt seed={template.id} />
    </div>
  );
}

export function WorkflowGallery() {
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    listTemplates()
      .then((all) => setTemplates(all.filter((t) => t.kind === "template")))
      .catch(() => setTemplates([]));
  }, []);

  async function start(t: Template) {
    if (busy) return;
    setBusy(t.id);
    track("template_selected", { id: t.id, name: t.name, kind: t.kind, from: "workflows" });
    try {
      // Saved first, then opened by id: the canvas loads the graph from the project, so the
      // nodes are already wired when it paints — no "apply a template" step to remember.
      const { id } = await createAgent(t.name, t.graph);
      router.push(`/canvas?agent=${id}`);
    } catch {
      setBusy(null);
    }
  }

  return (
    <div className="w-full max-w-6xl px-10 py-8">
      <h1 className="font-heading text-2xl">Workflows</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Ready-made agents for a job. Pick one and it opens as a new project you can edit.
      </p>

      {templates === null ? (
        <p className="mt-8 text-sm text-muted-foreground">Loading…</p>
      ) : templates.length === 0 ? (
        <p className="mt-8 text-sm text-muted-foreground" data-testid="workflows-empty">
          Couldn&rsquo;t load the workflow library. Start from a template on the{" "}
          <a href="/canvas" className="underline">
            canvas
          </a>{" "}
          instead.
        </p>
      ) : (
        // One flat grid. The API still ships these in category order, so related workflows sit
        // together and study leads — the grouping survives as sequence once the headings go.
        <div
          className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4"
          data-testid="workflow-grid"
        >
          {templates.map((t) => (
            <button
              type="button"
              key={t.id}
              onClick={() => void start(t)}
              disabled={busy !== null}
              data-testid="workflow-card"
              data-category={t.category}
              aria-label={t.name}
              className="group overflow-hidden rounded-lg border border-border bg-card text-left transition hover:border-foreground/25 disabled:opacity-50"
            >
              <WorkflowThumb template={t} />
              <div className="p-3">
                <div className="truncate text-[13px] font-medium">
                  {busy === t.id ? "Opening…" : t.name}
                </div>
                <div className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                  {t.description}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
