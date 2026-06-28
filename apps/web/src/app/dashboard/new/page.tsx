"use client";

import type { GraphSpec } from "@calypr/dsl";
import { ArrowLeft, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { createAgent, listTemplates, type Template } from "@/lib/api";
import { DEFAULT_CONFIG } from "@/lib/graph";

// A minimal Input → Agent → Output starter for a "blank" project.
function blankGraph(): GraphSpec {
  return {
    schema_version: "0.1.0",
    id: "canvas-agent",
    name: "Untitled Agent",
    state: [
      { key: "input", type: "string", reducer: "last" },
      { key: "messages", type: "messages", reducer: "append" },
      { key: "output", type: "string", reducer: "last" },
    ],
    nodes: [
      {
        id: "in",
        type: "input",
        config: { input_channel: "input", target_channel: "messages" },
      },
      { id: "agent", type: "agent", config: { ...DEFAULT_CONFIG.agent } },
      {
        id: "out",
        type: "output",
        config: { source_channel: "messages", output_channel: "output" },
      },
    ],
    edges: [
      { id: "e1", source: "in", target: "agent" },
      { id: "e2", source: "agent", target: "out" },
    ],
    entry: "in",
  };
}

export default function NewProjectPage() {
  const router = useRouter();
  const [name, setName] = useState("Untitled Agent");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, []);

  async function start(graph: GraphSpec, fallbackName: string) {
    if (busy) return;
    setBusy(true);
    try {
      const { id } = await createAgent(name.trim() || fallbackName, graph);
      router.push(`/canvas?agent=${id}`);
    } catch {
      setBusy(false);
    }
  }

  const groups: [string, Template[]][] = [
    ["Frameworks", templates.filter((t) => t.kind === "framework")],
    ["Templates", templates.filter((t) => t.kind === "template")],
  ];

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-8">
      <Link
        href="/dashboard"
        className={buttonVariants({ variant: "ghost", size: "sm" })}
      >
        <ArrowLeft className="h-4 w-4" /> Projects
      </Link>
      <h1 className="mt-4 text-2xl font-semibold">Start a new project</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Name it, then start from a blank canvas or a template.
      </p>

      <div className="mt-6 max-w-sm">
        <label htmlFor="np-name" className="text-sm font-medium">
          Project name
        </label>
        <Input
          id="np-name"
          className="mt-1.5"
          value={name}
          onChange={(e) => setName(e.target.value)}
          data-testid="new-name"
        />
      </div>

      <button
        type="button"
        onClick={() => start(blankGraph(), "Untitled Agent")}
        disabled={busy}
        data-testid="start-blank"
        className="mt-8 flex w-full items-center gap-3 rounded-lg border border-border bg-card p-4 text-left transition hover:border-foreground/20 disabled:opacity-50"
      >
        <span className="flex h-9 w-9 items-center justify-center rounded-md bg-muted">
          <Plus className="h-4 w-4" />
        </span>
        <span>
          <span className="block text-sm font-medium">Blank canvas</span>
          <span className="block text-xs text-muted-foreground">
            A starter Input → Agent → Output graph.
          </span>
        </span>
      </button>

      {groups.map(([label, list]) =>
        list.length ? (
          <section key={label} className="mt-8">
            <h2 className="text-sm font-medium text-muted-foreground">{label}</h2>
            <div
              className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
              data-testid={`gallery-${label.toLowerCase()}`}
            >
              {list.map((t) => (
                <button
                  type="button"
                  key={t.id}
                  onClick={() => start(t.graph, t.name)}
                  disabled={busy}
                  className="rounded-lg border border-border bg-card p-4 text-left transition hover:border-foreground/20 disabled:opacity-50"
                >
                  <div className="text-sm font-medium">{t.name}</div>
                  <div className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                    {t.description}
                  </div>
                </button>
              ))}
            </div>
          </section>
        ) : null,
      )}
    </div>
  );
}
