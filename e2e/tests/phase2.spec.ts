import { expect, test } from "@playwright/test";

// Phase 2 gate (CLAUDE-PLAN.md §11): build Input → Agent → Output on the canvas,
// configure the Agent, open the playground, send a message, and assert a streamed
// assistant reply renders. Uses the deterministic "fake" model (the Agent default),
// so the gate needs no API key and no database.
test("build an agent on the canvas and chat with it", async ({ page }) => {
  // Dev sign-in, then land on the canvas.
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  // Wait until React Flow has mounted client-side (palette handlers wired).
  await expect(page.locator(".react-flow__controls")).toBeVisible();

  // Build the chain — adding a block links it after the previous one.
  await page.getByTestId("add-input").click();
  await page.getByTestId("add-agent").click();
  await page.getByTestId("add-output").click();

  // Configure the Agent: select its node, confirm the (fake) model, set a prompt.
  await page.locator(".react-flow__node").filter({ hasText: "Agent" }).click();
  await expect(page.getByTestId("cfg-model")).toHaveValue("fake");
  await page.getByTestId("cfg-prompt").fill("You are concise.");

  // Open the playground and send a message.
  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("chat-input").fill("hello canvas");
  await page.getByTestId("chat-send").click();

  // A streamed assistant reply renders (the fake model echoes the user message).
  await expect(page.getByTestId("msg-assistant").last()).toContainText(
    "Echo: hello canvas",
    { timeout: 15_000 },
  );
});
