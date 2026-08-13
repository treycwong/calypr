import { expect, test } from "@playwright/test";

import { buildChain, signInAt } from "./helpers";

// Phase 2 gate (CLAUDE-PLAN.md §11): build Input → Agent → Output on the canvas,
// configure the Agent, open the playground, send a message, and assert a streamed
// assistant reply renders. Uses the deterministic "fake" model (the Agent default),
// so the gate needs no API key and no database.
test("build an agent on the canvas and chat with it", async ({ page }) => {
  // Dev sign-in, then land on the canvas.
  await signInAt(page, "/canvas");
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.getByTestId("canvas-toolbar")).toBeVisible();

  // Build the chain. Adding a block no longer wires it to anything — blocks can be dropped
  // anywhere, so every connection is drawn by hand; `buildChain` does both.
  await buildChain(page, ["input", "agent", "output"]);

  // Configure the Agent: select its node, switch to the keyless fake model (the default is now
  // gpt-4o-mini), set a prompt.
  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");
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
