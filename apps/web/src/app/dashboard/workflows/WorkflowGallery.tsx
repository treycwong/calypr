"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ProjectArt } from "@/components/dashboard/ProjectArt";
import { track } from "@/lib/analytics";
import { createAgent, listTemplates, type Template } from "@/lib/api";

import { UNSPLASH_UTM, WORKFLOW_PHOTOS } from "./photos";

/** The card's artwork: a cover photo, or generative art when a workflow has no photo yet.
 *
 *  Plain `<img>` rather than next/image — these are fixed-size decorative covers already sized
 *  by imgix, so the optimizer would add a remotePatterns entry and a round-trip through our own
 *  server for no gain. `loading="lazy"` because eighteen covers is eighteen requests, and only
 *  the first row is on screen. */
function WorkflowThumb({ template }: { template: Template }) {
  const photo = WORKFLOW_PHOTOS[template.id];
  return (
    <div className="aspect-[16/10] w-full overflow-hidden bg-muted">
      {photo ? (
        // eslint-disable-next-line @next/next/no-img-element -- next/image would add a
        // remotePatterns entry and route eighteen covers through the Vercel optimizer (billed
        // per transformation) to re-derive what imgix already did: these URLs are pinned to the
        // exact display size, webp, q80. The optimizer has nothing left to optimize.
        <img
          src={photo.src}
          alt={photo.alt}
          loading="lazy"
          decoding="async"
          className="h-full w-full object-cover transition duration-300 group-hover:scale-[1.03]"
        />
      ) : (
        // Seeded by template id, so a workflow with no cover still gets art that is its own and
        // never changes — and a new template is never blocked on someone picking a photo.
        <ProjectArt seed={template.id} />
      )}
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
          {templates.map((t) => {
            const photo = WORKFLOW_PHOTOS[t.id];
            return (
              // The card is a container, not a button: the photographer credit has to be a real
              // link, and a link inside a button is invalid and unreachable by keyboard. Instead
              // the button is stretched over the card and the credit sits above it.
              <div
                key={t.id}
                data-testid="workflow-card"
                data-category={t.category}
                className="group relative overflow-hidden rounded-lg border border-border bg-card transition hover:border-foreground/25"
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

                <button
                  type="button"
                  onClick={() => void start(t)}
                  disabled={busy !== null}
                  aria-label={t.name}
                  data-testid="workflow-open"
                  className="absolute inset-0 rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:cursor-default"
                />

                {photo ? (
                  // Above the stretched button so it stays clickable. Hidden until hover so the
                  // grid stays clean, but always in the DOM and reachable by keyboard.
                  <a
                    href={`${photo.href}${UNSPLASH_UTM}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-testid="workflow-credit"
                    className="absolute right-1.5 top-1.5 z-10 rounded bg-black/55 px-1.5 py-0.5 text-[10px] text-white/85 opacity-0 backdrop-blur-sm transition group-hover:opacity-100 focus-visible:opacity-100 hover:text-white"
                  >
                    {photo.by}
                  </a>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
