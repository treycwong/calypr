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
        /* next/image would add a remotePatterns entry and route eighteen covers through the
           Vercel optimizer (billed per transformation) to re-derive what imgix already did:
           these URLs are pinned to the exact display size, webp, q80. Nothing left to optimize.
           The directive has to be the line directly above the element — with the rationale
           inline it pointed at its own continuation comment and silently did nothing. */
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photo.src}
          alt={photo.alt}
          // A native tooltip, not an overlay: it names the photographer on hover without putting
          // a second click target on a card whose whole job is to be one.
          title={`Photo by ${photo.by} on Unsplash`}
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

/** Photographer credits for the covers on screen.
 *
 *  Unsplash's API guidelines ask that every displayed photo credit its photographer with a link
 *  to their profile. That credit used to sit on the card itself, which meant the most inviting
 *  part of a card — the photo — opened unsplash.com instead of the workflow. Collecting the
 *  credits here keeps the obligation and gives the cards back their whole surface.
 *
 *  Deduplicated and sorted: one photographer shooting two covers should be thanked once. */
function PhotoCredits({ templates }: { templates: Template[] }) {
  const people = new Map<string, string>();
  for (const t of templates) {
    const photo = WORKFLOW_PHOTOS[t.id];
    if (photo) people.set(photo.by, photo.href);
  }
  if (people.size === 0) return null;
  const credits = [...people.entries()].sort(([a], [b]) => a.localeCompare(b));

  return (
    <p className="mt-10 text-[11px] leading-relaxed text-muted-foreground" data-testid="photo-credits">
      Cover photos by{" "}
      {credits.map(([name, href], i) => (
        <span key={name}>
          {i > 0 ? (i === credits.length - 1 ? " and " : ", ") : null}
          <a
            href={`${href}${UNSPLASH_UTM}`}
            target="_blank"
            rel="noopener noreferrer"
            className="underline underline-offset-2 hover:text-foreground"
          >
            {name}
          </a>
        </span>
      ))}{" "}
      on{" "}
      <a
        href={`https://unsplash.com${UNSPLASH_UTM}`}
        target="_blank"
        rel="noopener noreferrer"
        className="underline underline-offset-2 hover:text-foreground"
      >
        Unsplash
      </a>
      .
    </p>
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
          {/* The whole card is one button. An earlier version floated the photographer credit
              over the corner, which made a link out of the one place a cover photo invites you to
              click — the credit now lives under the grid, where it can be a real link without
              taking a bite out of the card. */}
          {templates.map((t) => (
            <button
              type="button"
              key={t.id}
              onClick={() => void start(t)}
              disabled={busy !== null}
              data-testid="workflow-card"
              data-category={t.category}
              aria-label={t.name}
              className="group overflow-hidden rounded-lg border border-border bg-card text-left transition hover:border-foreground/25 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none disabled:opacity-50"
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

      {templates?.length ? <PhotoCredits templates={templates} /> : null}
    </div>
  );
}
