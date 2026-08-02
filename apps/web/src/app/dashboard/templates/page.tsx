import type { Metadata } from "next";

export const metadata: Metadata = { title: "Templates — Calypr" };

// A placeholder on purpose. The starter gallery already exists on the canvas (`GET /templates`);
// this tab is where saved, workspace-owned templates will live, and shipping the nav entry now
// keeps the sidebar stable rather than moving under people later.
export default function TemplatesPage() {
  return (
    <div className="mx-auto max-w-3xl px-8 py-10">
      <h1 className="font-heading text-2xl">Templates</h1>
      <p className="mt-4 text-sm text-muted-foreground" data-testid="templates-empty">
        Saved templates are coming soon. For now, start from a template on the{" "}
        <a href="/canvas" className="underline">
          canvas
        </a>
        .
      </p>
    </div>
  );
}
