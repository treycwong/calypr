"use client";

import { Check, Copy, Download, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import type { GraphSpec } from "@calypr/dsl";

import { Button } from "@/components/ui/button";
import { track } from "@/lib/analytics";
import { generateCode } from "@/lib/api";

// Slugify the project name into a python filename (e.g. "Travel App" → "travel_app.py").
function fileName(name?: string) {
  const slug = (name ?? "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return `${slug || "agent"}.py`;
}

export function CodeView({
  getGraph,
  name,
}: {
  getGraph: () => GraphSpec;
  name?: string;
}) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  async function refresh() {
    setBusy(true);
    setError("");
    try {
      setCode(await generateCode(getGraph()));
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
        if (active) setCode(c);
      })
      .catch(() => {
        if (active) setError("Could not generate code.");
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div className="min-w-0">
          <div className="truncate font-mono text-sm font-medium" title={fileName(name)}>
            {fileName(name)}
          </div>
          <div className="text-[11px] text-muted-foreground">Python · LangGraph</div>
        </div>
        <div className="flex shrink-0 gap-0.5">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => void refresh()}
            data-testid="code-refresh"
            disabled={busy}
            aria-label="Regenerate code"
            title="Regenerate"
          >
            <RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />
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
      <pre
        className="flex-1 overflow-auto bg-card p-3 font-mono text-xs leading-relaxed"
        data-testid="code-output"
      >
        {error ? error : code ? code : "Generating…"}
      </pre>
    </div>
  );
}
