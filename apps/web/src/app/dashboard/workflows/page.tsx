import type { Metadata } from "next";

import { WorkflowGallery } from "./WorkflowGallery";

export const metadata: Metadata = { title: "Workflows — Calypr" };

// The workflow library: every use-case starter, grouped by the job it does.
//
// Frameworks (ReAct, RAG, reflection…) are deliberately absent. They are the architecture an
// agent is built *on*, chosen while wiring a canvas — not a job someone browses for. They stay
// on the canvas's Templates rail, where the choice is in front of the thing it affects.
export default function WorkflowsPage() {
  return <WorkflowGallery />;
}
