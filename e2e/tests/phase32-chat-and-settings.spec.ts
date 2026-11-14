/**
 * The chat and a block's settings share the right panel as tabs (CAL-7).
 *
 * The chat used to *replace* the right panel, so with the chat open a block click selected the
 * block and showed nothing. Arriving from a template opens the chat (#109), so every newcomer hit
 * that in their first minute.
 */
import { expect, test, type Page } from "@playwright/test";

import { buildChain, openCanvas } from "./helpers";

async function buildAgent(page: Page) {
  await buildChain(page, ["input", "agent", "output"]);
  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");
  await expect(page.getByTestId("cfg-model")).toHaveValue("fake");
}

test("with the chat open, clicking a block shows its settings, and Chat is one click away", async ({
  page,
}) => {
  await openCanvas(page);
  await buildAgent(page);

  await page.getByTestId("toggle-playground").click();
  await expect(page.getByTestId("playground")).toBeVisible();
  await page.getByTestId("chat-input").fill("keep me");
  await page.getByTestId("chat-send").click();
  await expect(page.getByTestId("msg-assistant").last()).toContainText("Echo: keep me", {
    timeout: 30_000,
  });

  // The bug: this click used to select the block and show nothing.
  await page.getByTestId("node-agent").click();
  await expect(page.getByTestId("config-panel")).toBeVisible();
  await expect(page.getByTestId("cfg-model")).toHaveValue("fake");
  await expect(page.getByTestId("playground")).toBeHidden();

  // One click back, and the conversation is still there: the chat is hidden, never unmounted.
  await page.getByTestId("tab-right-chat").click();
  await expect(page.getByTestId("playground")).toBeVisible();
  await expect(page.getByTestId("msg-user").last()).toContainText("keep me");
  await expect(page.getByTestId("msg-assistant").last()).toContainText("Echo: keep me");
});

test("a click on empty canvas goes back to the chat; the header button returns to it too", async ({
  page,
}) => {
  await openCanvas(page);
  await buildAgent(page);
  await page.getByTestId("toggle-playground").click();

  await page.getByTestId("node-agent").click();
  await expect(page.getByTestId("config-panel")).toBeVisible();
  await page.locator(".react-flow__pane").click({ position: { x: 40, y: 260 } });
  await expect(page.getByTestId("playground")).toBeVisible();

  // From Properties, the header Chat button brings the chat forward rather than closing it.
  await page.getByTestId("node-agent").click();
  await page.getByTestId("toggle-playground").click();
  await expect(page.getByTestId("playground")).toBeVisible();

  // From the Chat tab it closes, handing the panel back to the selected block.
  await page.getByTestId("toggle-playground").click();
  await expect(page.getByTestId("playground")).toHaveCount(0);
  await expect(page.getByTestId("config-panel")).toBeVisible();
  await expect(page.getByTestId("tab-right-chat")).toHaveCount(0);
});
