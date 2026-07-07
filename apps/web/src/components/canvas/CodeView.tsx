"use client";

import { useEffect, useState } from "react";

import type { GraphSpec } from "@calypr/dsl";

import { Button } from "@/components/ui/button";
import { track } from "@/lib/analytics";
import { generateCode } from "@/lib/api";

export function CodeView({ getGraph }: { getGraph: () => GraphSpec }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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

  function download() {
    track("code_downloaded", { bytes: code.length }); // ceiling event
    const blob = new Blob([code], { type: "text/x-python" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "agent.py";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <span className="text-sm font-medium">Code · Python (LangGraph)</span>
        <div className="flex gap-1.5">
          <Button
            size="sm"
            variant="ghost"
            onClick={() => void refresh()}
            data-testid="code-refresh"
            disabled={busy}
          >
            Refresh
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              track("code_copied", { bytes: code.length }); // ceiling event
              void navigator.clipboard.writeText(code);
            }}
            disabled={!code}
          >
            Copy
          </Button>
          <Button size="sm" variant="ghost" onClick={download} disabled={!code}>
            Download
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
