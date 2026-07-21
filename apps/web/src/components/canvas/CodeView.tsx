"use client";

import { Check, Copy, Download, RefreshCw, Undo2, Wand2 } from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import type { GraphSpec } from "@calypr/dsl";

import { Button } from "@/components/ui/button";
import { track } from "@/lib/analytics";
import { generateCode, parseCode } from "@/lib/api";
import { roundtripEnabled } from "@/lib/flags";

// Slugify the project name into a python filename (e.g. "Travel App" → "travel_app.py").
function fileName(name?: string) {
  const slug = (name ?? "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return `${slug || "agent"}.py`;
}

export function CodeView({
  getGraph,
  name,
  applyGraph,
}: {
  getGraph: () => GraphSpec;
  name?: string;
  /** Load a parsed graph back onto the canvas. Absent → the round-trip UI stays hidden. */
  applyGraph?: (spec: GraphSpec) => void;
}) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  // Round-trip state: the code differs from what we generated, and what the last apply found.
  const [dirty, setDirty] = useState(false);
  const [applying, setApplying] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "warn" | "error"; text: string } | null>(
    null,
  );
  const editedTracked = useRef(false);

  // The gate can come from localStorage, which doesn't exist on the server — read it as an
  // external store so the server renders "off" and the client corrects after hydration, with
  // no mismatch and no setState-in-effect. It can't change mid-session, so there's nothing
  // to subscribe to.
  const gateOpen = useSyncExternalStore(
    () => () => {},
    roundtripEnabled,
    () => false,
  );

  // The round-trip needs both the gate and a canvas to apply to.
  const canRoundTrip = gateOpen && typeof applyGraph === "function";

  function adopt(next: string) {
    setCode(next);
    setDirty(false);
    setNotice(null);
    editedTracked.current = false;
  }

  async function refresh() {
    setBusy(true);
    setError("");
    try {
      adopt(await generateCode(getGraph()));
    } catch {
      setError("Could not generate code.");
    } finally {
      setBusy(false);
    }
  }

  // Generate once when the panel opens. Async so no setState runs synchronously in
  // the effect body (React 19 set-state-in-effect rule).
  useEffect(() => {
    let active = true;
    track("code_view_opened"); // ceiling event: the user looked at the code they own
    generateCode(getGraph())
      .then((c) => {
        if (active) adopt(c);
      })
      .catch(() => {
        if (active) setError("Could not generate code.");
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function edit(next: string) {
    setCode(next);
    setDirty(true);
    setNotice(null);
    // Ceiling-resolution funnel starts here — fire once per edit session, not per keystroke.
    if (!editedTracked.current) {
      editedTracked.current = true;
      track("code_edited");
    }
  }

  async function apply() {
    if (!applyGraph) return;
    setApplying(true);
    setNotice(null);
    try {
      const result = await parseCode(code);
      if (!result.graph.nodes?.length) {
        // Nothing recoverable — almost always a syntax error the parser reported as a warning.
        track("parse_failed", { reason: result.warnings[0] ?? "no nodes" });
        setNotice({
          kind: "error",
          text: result.warnings[0] ?? "Could not read a graph from this code.",
        });
        return;
      }
      applyGraph(result.graph);
      setDirty(false);
      editedTracked.current = false;

      const degraded = result.degraded_nodes.length;
      if (degraded) {
        // Honest metric: we applied it, but N nodes came back as Custom Code blocks.
        track("parse_degraded", { degraded_nodes: degraded });
        setNotice({
          kind: "warn",
          text: `Applied. ${degraded} ${degraded === 1 ? "step" : "steps"} kept as custom code — ${result.degraded_nodes.join(", ")}.`,
        });
      } else {
        setNotice({ kind: "ok", text: "Applied to canvas." });
      }
      track("parse_applied", {
        nodes: result.graph.nodes.length,
        edges: result.graph.edges?.length ?? 0,
        degraded_nodes: degraded,
      });
    } catch {
      track("parse_failed", { reason: "request failed" });
      setNotice({ kind: "error", text: "Could not apply this code to the canvas." });
    } finally {
      setApplying(false);
    }
  }

  function copy() {
    track("code_copied", { bytes: code.length }); // ceiling event
    void navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  function download() {
    track("code_downloaded", { bytes: code.length }); // ceiling event
    const blob = new Blob([code], { type: "text/x-python" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName(name);
    a.click();
    URL.revokeObjectURL(url);
  }

  const noticeTone =
    notice?.kind === "error"
      ? "text-destructive"
      : notice?.kind === "warn"
        ? "text-amber-600 dark:text-amber-500"
        : "text-emerald-600 dark:text-emerald-500";

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div className="min-w-0">
          <div className="truncate font-mono text-sm font-medium" title={fileName(name)}>
            {fileName(name)}
          </div>
          <div className="text-[11px] text-muted-foreground">
            Python · LangGraph{canRoundTrip ? " · editable" : ""}
          </div>
        </div>
        <div className="flex shrink-0 gap-0.5">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => void refresh()}
            data-testid="code-refresh"
            disabled={busy}
            aria-label={dirty ? "Discard edits and regenerate code" : "Regenerate code"}
            title={dirty ? "Discard edits" : "Regenerate"}
          >
            {dirty ? (
              <Undo2 className="h-4 w-4" />
            ) : (
              <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
            )}
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={copy}
            disabled={!code}
            aria-label="Copy code"
            title={copied ? "Copied" : "Copy"}
          >
            {copied ? (
              <Check className="h-4 w-4 text-emerald-500" />
            ) : (
              <Copy className="h-4 w-4" />
            )}
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={download}
            disabled={!code}
            aria-label="Download code"
            title="Download"
          >
            <Download className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {canRoundTrip ? (
        <textarea
          className="flex-1 resize-none overflow-auto bg-card p-3 font-mono text-xs leading-relaxed outline-none focus-visible:ring-1 focus-visible:ring-ring"
          data-testid="code-output"
          value={error ? error : code}
          onChange={(e) => edit(e.target.value)}
          spellCheck={false}
          aria-label="Generated Python — edit and apply back to the canvas"
        />
      ) : (
        <pre
          className="flex-1 overflow-auto bg-card p-3 font-mono text-xs leading-relaxed"
          data-testid="code-output"
        >
          {error ? error : code ? code : "Generating…"}
        </pre>
      )}

      {canRoundTrip ? (
        <div className="flex items-center gap-2 border-t border-border px-3 py-2">
          <Button
            size="sm"
            onClick={() => void apply()}
            disabled={!code || applying || !dirty}
            data-testid="apply-to-canvas"
            title={dirty ? "Apply these edits to the canvas" : "Edit the code to apply it"}
          >
            <Wand2 className="mr-1.5 h-3.5 w-3.5" />
            {applying ? "Applying…" : "Apply to canvas"}
          </Button>
          {notice ? (
            <span className={`min-w-0 flex-1 truncate text-[11px] ${noticeTone}`} data-testid="parse-notice" title={notice.text}>
              {notice.text}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
