import { expect, type Page, test } from "@playwright/test";

// Phase 2c: the config panel lets you reach what the engine can actually do.
//
// `test_config_panel_coverage.py` proves every field has a control; these prove the controls
// that were missing entirely now work — a setting has to survive into the graph, not just
// render. The agent-type picker is the headline: its options existed in graph.ts with six
// written labels and nothing rendered them, so a hand-built Agent was stuck on `model_based`
// and the goal/reflection fields below it could never appear.

async function canvasWithAgent(page: Page) {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page.locator(".react-flow__controls")).toBeVisible();
  await page.getByTestId("add-input").click();
  await page.getByTestId("add-agent").click();
  await page.getByTestId("add-output").click();
  await page.getByTestId("node-agent").click();
}

test("the agent type is selectable, and its dependent fields follow", async ({ page }) => {
  await canvasWithAgent(page);

  const type = page.getByTestId("cfg-agent-type");
  await expect(type).toHaveValue("model_based");
  // model_based has no extra fields — the conditional ones are for other rungs of the ladder.
  await expect(page.getByTestId("cfg-goal")).toHaveCount(0);

  await type.selectOption("goal_based");
  await page.getByTestId("cfg-goal").fill("Book the cheapest flight");
  await expect(page.getByTestId("cfg-goal")).toHaveValue("Book the cheapest flight");

  await type.selectOption("reflection");
  await expect(page.getByTestId("cfg-max-reflections")).toBeVisible();
  await expect(page.getByTestId("cfg-reflection-criteria")).toBeVisible();
  await expect(page.getByTestId("cfg-goal")).toHaveCount(0);

  await type.selectOption("utility_based");
  await expect(page.getByTestId("cfg-num-candidates")).toBeVisible();
});

test("the agent type reaches the generated code", async ({ page }) => {
  // The real proof it's wired: the picker changes the artifact, not just the panel.
  await canvasWithAgent(page);
  await page.getByTestId("cfg-agent-type").selectOption("goal_based");
  await page.getByTestId("cfg-goal").fill("Refund the customer");

  await page.getByTestId("toggle-code").click();
  await expect(page.getByTestId("code-output")).toContainText("Refund the customer", {
    timeout: 15_000,
  });
});

test("temperature and max tokens are reachable and persist", async ({ page }) => {
  await canvasWithAgent(page);

  // Behind a disclosure: the panel opens on what the block does, not on sampling parameters.
  await expect(page.getByTestId("cfg-temperature")).not.toBeVisible();
  await page.getByTestId("cfg-advanced").click();

  await page.getByTestId("cfg-temperature").fill("0.2");
  await page.getByTestId("cfg-max-tokens").fill("256");

  // Deselect and come back: the values belong to the node, not the panel's local state.
  await page.getByTestId("node-input").click();
  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-advanced").click();
  await expect(page.getByTestId("cfg-temperature")).toHaveValue("0.2");
  await expect(page.getByTestId("cfg-max-tokens")).toHaveValue("256");
});

test("a custom code block can declare its imports", async ({ page }) => {
  // Without this the escape hatch couldn't reach the standard library: the engine honoured
  // `imports` and there was no way to set it.
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page.locator(".react-flow__controls")).toBeVisible();
  await page.getByTestId("add-input").click();
  await page.getByTestId("add-code").click();
  await page.getByTestId("add-output").click();
  await page.getByTestId("node-code").click();

  await page.getByTestId("cfg-imports").fill("import json\nfrom datetime import datetime");
  await page.getByTestId("cfg-code").fill("return {'output': json.dumps({'ok': True})}");

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("import json", { timeout: 15_000 });
  await expect(code).toContainText("from datetime import datetime");
});
