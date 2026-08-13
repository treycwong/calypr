import { expect, test } from "@playwright/test";

import { buildChain, openCode, signInAt } from "./helpers";

// Phase 3 gate (realignment §Phase 3): the canvas projects to ownable Python, and a
// Custom Code node round-trips verbatim into the generated code (the no-ceiling escape
// hatch). Viewing code needs no API key and no database.
test("the canvas projects to ownable Python with a Custom Code escape hatch", async ({
  page,
}) => {
  await signInAt(page, "/canvas");
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.getByTestId("canvas-toolbar")).toBeVisible();

  // Build Input → Agent → Custom Code → Output (a sensible linear chain), wiring it by hand:
  // adding a block no longer connects it to anything.
  await buildChain(page, ["input", "agent", "code", "output"]);

  // Open the Code view — idiomatic LangGraph, with the custom code emitted verbatim.
  await openCode(page);
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  await expect(code).toContainText("StateGraph");
  await expect(code).toContainText("init_chat_model"); // the agent
  await expect(code).toContainText(".upper()"); // the custom code, round-tripped
});
