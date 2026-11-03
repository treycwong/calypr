"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { track } from "@/lib/analytics";
import { CapReachedError, createAgent, listTemplates, type Template } from "@/lib/api";

/** How many to offer. Enough to show the range (study, images, research, support) without
 *  turning the empty state into the gallery /dashboard/new already is. */
const COUNT = 4;

/** One-click starters for an account with no projects yet.
 *
 *  The walkthrough of 2026-11-03 found the empty dashboard saying "start from a template" with
 *  no template on screen: the newcomer had to find New Project, then scroll past ten frameworks
 *  to reach one. These create the project and open it with the chat ready, same as picking it on
 *  /dashboard/new.
 *
 *  Picked as **the first template of each category**, in the API's order (study first), rather
 *  than a list of ids here — a second hand-kept list of templates is exactly what drifts. */
export function StarterTemplates({ onCapped }: { onCapped: () => void }) {
  const router = useRouter();
  const [templates, setTemplates] = useState<Template[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listTemplates()
      .then((all) => {
        const seen = new Set<string>();
        const picks: Template[] = [];
        for (const t of all) {
          if (t.kind !== "template" || seen.has(t.category)) continue;
          seen.add(t.category);
          picks.push(t);
        }
        setTemplates(picks.slice(0, COUNT));
      })
      .catch(() => setTemplates([]));
  }, []);

  async function start(t: Template) {
    if (busy) return;
    setBusy(true);
    try {
      const { id } = await createAgent(t.name, t.graph);
      track("starter_template_used", { template: t.id, from: "dashboard-empty" });
      router.push(`/canvas?agent=${id}&starter=${encodeURIComponent(t.id)}`);
    } catch (err) {
      setBusy(false);
      if (err instanceof CapReachedError) onCapped();
    }
  }

  if (templates.length === 0) return null;

  return (
    <div className="mt-6 w-full max-w-2xl px-6" data-testid="starter-templates">
      <p className="text-xs text-muted-foreground">Or run one of these in one click:</p>
      <div className="mt-3 grid gap-2 text-left sm:grid-cols-2">
        {templates.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => void start(t)}
            disabled={busy}
            className="rounded-lg border border-border bg-card p-3 transition hover:border-foreground/20 disabled:opacity-50"
          >
            <div className="text-sm font-medium">{t.name}</div>
            <div className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
              {t.description}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
