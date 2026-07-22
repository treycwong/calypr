import { expect, test } from "@playwright/test";

// The workspace default model (Settings → Workspace). Blocks ship `model: ""` — inherit — so
// this one setting decides what the whole canvas runs on, and an untouched workspace has to
// land on a real model rather than the `fake` test seam that answers "Echo: …".

test("the Workspace tab exposes the default model picker", async ({ page }) => {
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  const picker = page.getByTestId("ws-default-model");
  await expect(picker).toBeVisible();
  // "" is the inherit sentinel, and the label has to name what it actually resolves to —
  // "Workspace default → ?" would tell the user nothing.
  await expect(picker.locator("option[value='']")).toContainText("gpt-4o-mini");
  await expect(picker.locator("option[value='gpt-4o']")).toHaveCount(1);
});

test("the default model saves and survives a reload", async ({ page }) => {
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  const picker = page.getByTestId("ws-default-model");
  await picker.selectOption("gpt-4o");
  await expect(page.getByText("Saved ✓")).toBeVisible();

  await page.reload();
  await page.getByTestId("tab-workspace").click();
  await expect(page.getByTestId("ws-default-model")).toHaveValue("gpt-4o");

  // Put it back so the shared dev workspace doesn't leak this choice into other specs.
  await page.getByTestId("ws-default-model").selectOption("");
  await expect(page.getByText("Saved ✓")).toBeVisible();
});

test("a new Agent block inherits instead of naming a model", async ({ page }) => {
  // The canvas half of the same rule: dragging a block on and never opening its config must
  // still produce a working agent. Router/Evaluator/Memory/Responder/Revisor used to default
  // to `fake` here, which shipped canned "Echo:" answers to anyone who used them.
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page.locator(".react-flow__controls")).toBeVisible();

  await page.getByTestId("add-agent").click();
  await page.getByTestId("node-agent").click();
  await expect(page.getByTestId("cfg-model")).toHaveValue("");
});
