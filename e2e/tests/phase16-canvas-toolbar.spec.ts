import { expect, test } from "@playwright/test";

import { openCanvas } from "./helpers";

// The canvas toolbar replaced React Flow's stock <Controls /> and <MiniMap />: one bar carrying
// the arrow/hand tools, undo/redo, and a zoom readout. Undo/redo behaviour itself is covered by
// phase5 (the testids moved here but kept their names); these cover the parts that are new.

test("the toolbar replaces React Flow's stock controls and minimap", async ({ page }) => {
  await openCanvas(page);

  await expect(page.getByTestId("canvas-toolbar")).toBeVisible();
  await expect(page.locator(".react-flow__controls")).toHaveCount(0);
  await expect(page.locator(".react-flow__minimap")).toHaveCount(0);
});

test("V and H switch between the arrow and hand tools", async ({ page }) => {
  await openCanvas(page);

  const select = page.getByTestId("tool-select");
  const pan = page.getByTestId("tool-pan");

  // The arrow is the default.
  await expect(select).toHaveAttribute("aria-pressed", "true");
  await expect(pan).toHaveAttribute("aria-pressed", "false");

  await page.keyboard.press("h");
  await expect(pan).toHaveAttribute("aria-pressed", "true");
  await expect(select).toHaveAttribute("aria-pressed", "false");
  // The pane advertises the grab cursor while the hand is active.
  await expect(page.locator(".react-flow.canvas-pan")).toBeVisible();

  await page.keyboard.press("v");
  await expect(select).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".react-flow.canvas-pan")).toHaveCount(0);

  // Clicking works too, not just the shortcuts.
  await pan.click();
  await expect(pan).toHaveAttribute("aria-pressed", "true");
});

test("the tool shortcuts are ignored while typing", async ({ page }) => {
  await openCanvas(page);

  // The agent-name field is a plain input in the header — typing "h" there must not grab the
  // canvas out from under the cursor.
  const nameField = page.getByTestId("agent-name");
  await nameField.fill("");
  await nameField.pressSequentially("hv");

  await expect(nameField).toHaveValue("hv");
  await expect(page.getByTestId("tool-select")).toHaveAttribute("aria-pressed", "true");
});

test("the zoom menu steps the zoom level in and out", async ({ page }) => {
  await openCanvas(page);

  const level = page.getByTestId("zoom-level");
  await expect(level).toBeVisible();

  const read = async () => Number((await level.innerText()).replace("%", ""));
  const start = await read();

  await page.getByTestId("zoom-menu").click();
  await page.getByTestId("zoom-in").click();
  await expect.poll(read).toBeGreaterThan(start);

  const zoomedIn = await read();
  await page.getByTestId("zoom-menu").click();
  await page.getByTestId("zoom-out").click();
  await expect.poll(read).toBeLessThan(zoomedIn);
});

test("the + and - keys zoom the canvas", async ({ page }) => {
  await openCanvas(page);

  const level = page.getByTestId("zoom-level");
  const read = async () => Number((await level.innerText()).replace("%", ""));
  const start = await read();

  await page.keyboard.press("+");
  await expect.poll(read).toBeGreaterThan(start);

  const zoomedIn = await read();
  await page.keyboard.press("-");
  await expect.poll(read).toBeLessThan(zoomedIn);
});
