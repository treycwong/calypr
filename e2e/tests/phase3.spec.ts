import { expect, test } from "@playwright/test";

// Phase 3 gate (realignment §Phase 3): the canvas projects to ownable Python, and a
// Custom Code node round-trips verbatim into the generated code (the no-ceiling escape
// hatch). Viewing code needs no API key and no database.
test("the canvas projects to ownable Python with a Custom Code escape hatch", async ({
  page,
}) => {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  // Wait until React Flow has mounted client-side, so the palette handlers are wired
  // (avoids a hydration race where the first clicks are lost under load).
  await expect(page.locator(".react-flow__controls")).toBeVisible();

  // Build Input → Agent → Custom Code → Output (a sensible linear chain). Gate each add
  // on the node mounting so no click is lost under parallel load.
  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-agent").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await page.getByTestId("add-code").click();
  await expect(page.getByTestId("node-code")).toBeVisible();
  await page.getByTestId("add-output").click();
  await expect(page.getByTestId("node-output")).toBeVisible();

  // Open the Code view — idiomatic LangGraph, with the custom code emitted verbatim.
  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  await expect(code).toContainText("StateGraph");
  await expect(code).toContainText("init_chat_model"); // the agent
  await expect(code).toContainText(".upper()"); // the custom code, round-tripped
});
