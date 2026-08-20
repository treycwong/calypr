"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ProjectArt } from "@/components/dashboard/ProjectArt";
import { track } from "@/lib/analytics";
import { createAgent, listTemplates, type Template } from "@/lib/api";

/** Categories render in the order the API's own taxonomy declares, with anything uncategorized
 *  last — a new workflow shipped without a category is visible and obviously unfiled, rather
 *  than silently missing from the page. */
const UNFILED = "More";

function group(templates: Template[]): [string, Template[]][] {
  const order: string[] = [];
  const by = new Map<string, Template[]>();
  for (const t of templates) {
    const key = t.category || UNFILED;
    if (!by.has(key)) {
      by.set(key, []);
      order.push(key);
    }
    by.get(key)!.push(t);
  }
  // UNFILED sinks to the bottom wherever it first appeared.
  order.sort((a, b) => Number(a === UNFILED) - Number(b === UNFILED));
  return order.map((k) => [k, by.get(k)!]);
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
      const { id } = await createAgent(t.name, t.graph);
      router.push(`/canvas?agent=${id}`);
    } catch {
      setBusy(null);
    }
  }

  return (
    <div className="w-full max-w-5xl px-10 py-8">
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
        group(templates).map(([category, list]) => (
          <section key={category} className="mt-9">
            <h2 className="font-mono text-xs font-medium uppercase tracking-[0.15em] text-muted-foreground">
              {category}
            </h2>
            <div
              className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
              data-testid="workflow-group"
              data-category={category}
            >
              {list.map((t) => (
                <button
                  type="button"
                  key={t.id}
                  onClick={() => void start(t)}
                  disabled={busy !== null}
                  data-testid="workflow-card"
                  aria-label={t.name}
                  className="group overflow-hidden rounded-xl border border-border bg-card text-left transition hover:border-foreground/25 disabled:opacity-50"
                >
                  {/* Seeded by the template id, so a workflow's art never changes and no two
                      look alike — the same trick the project cards use to make a wall of
                      near-identical graphs findable at a glance. */}
                  <div className="h-28 w-full overflow-hidden">
                    <ProjectArt seed={t.id} />
                  </div>
                  <div className="p-4">
                    <div className="text-sm font-medium">
                      {busy === t.id ? "Opening…" : t.name}
                    </div>
                    <div className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                      {t.description}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
