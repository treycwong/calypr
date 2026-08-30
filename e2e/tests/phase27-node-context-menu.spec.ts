import { expect, test } from "@playwright/test";

import { addNode, buildChain, openCanvas } from "./helpers";

/** The Video block is Plus-only, so a default (free) e2e workspace can't place one — that gate is
 *  tested in `phase23-paid-blocks.spec.ts`. */
async function asPlus(page: import("@playwright/test").Page) {
  await page.route("**/api/workspace", async (route) => {
    const res = await route.fetch();
    const body = await res.json().catch(() => ({}));
    return route.fulfill({ json: { ...body, plan: "plus" } });
  });
}

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

// The right-click menu on a block: Duplicate, Copy, Copy/Paste settings, Delete.
//
// It is the discoverable half of the keyboard shortcuts added alongside it — a shortcut you have
// to already know about is not a feature most people find. `phase26` covers the shortcuts
// themselves; this covers the menu and the two things only it can do (settings transfer, and
// acting on a block that wasn't already selected).

const open = async (page: import("@playwright/test").Page, testid: string) => {
  // `.first()`: several blocks of a kind can be on the canvas once things have been duplicated.
  await page.getByTestId(testid).first().click({ button: "right" });
  await expect(page.getByTestId("node-context-menu")).toBeVisible();
};

test("right-clicking a block offers duplicate, copy, settings and delete", async ({ page }) => {
  await openCanvas(page);
  await addNode(page, "image");
  await open(page, "node-image");

  const menu = page.getByTestId("node-context-menu");
  await expect(menu.getByTestId("ctx-duplicate")).toBeVisible();
  await expect(menu.getByTestId("ctx-copy")).toBeVisible();
  await expect(menu.getByTestId("ctx-copy-settings")).toBeVisible();
  await expect(menu.getByTestId("ctx-delete")).toBeVisible();
  // Nothing has been copied yet, so there is nothing to paste.
  await expect(menu.getByTestId("ctx-paste-settings")).toBeDisabled();
});

test("duplicate and delete work from the menu", async ({ page }) => {
  await openCanvas(page);
  await addNode(page, "image");

  await open(page, "node-image");
  await page.getByTestId("ctx-duplicate").click();
  await expect(page.locator(".react-flow__node")).toHaveCount(2);

  await open(page, "node-image");
  await page.getByTestId("ctx-delete").click();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);

  // Both are undoable, like every other canvas mutation.
  await page.keyboard.press("ControlOrMeta+z");
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
});

test("deleting a block takes its wires with it", async ({ page }) => {
  await openCanvas(page);
  await buildChain(page, ["input", "image", "output"]);
  await expect(page.locator("g.react-flow__edge")).toHaveCount(2);

  await open(page, "node-image");
  await page.getByTestId("ctx-delete").click();

  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  // Both wires went with it. An edge left pointing at a block that no longer exists renders as a
  // stub attached to nothing.
  await expect(page.locator("g.react-flow__edge")).toHaveCount(0);
});

test("settings copy from one block to another of the same type", async ({ page }) => {
  await openCanvas(page);
  await addNode(page, "image");
  await page.getByTestId("node-image").click();
  const style = page.getByTestId("config-panel").locator("#cfg-style");
  await style.fill("SHARED-STYLE");

  // A second Image block, left at its defaults. Added straight from the palette rather than
  // through `addNode`, whose visibility assertion is strict-mode-bound and can't see past a
  // second block of the same kind.
  await page.getByTestId("add-image").click();
  const blocks = page.getByTestId("node-image");
  await expect(blocks).toHaveCount(2);
  await blocks.nth(1).click();
  await expect(style).toHaveValue("");

  await blocks.first().click({ button: "right" });
  await page.getByTestId("ctx-copy-settings").click();

  await blocks.nth(1).click({ button: "right" });
  await page.getByTestId("ctx-paste-settings").click();

  await blocks.nth(1).click();
  await expect(style).toHaveValue("SHARED-STYLE");
});

test("settings cannot be pasted onto a different kind of block", async ({ page }) => {
  // Configs are not interchangeable — writing an Image config onto a Video block would set fields
  // it doesn't have and drop every field it does, leaving a block that looks configured and
  // cannot run.
  await asPlus(page);
  await openCanvas(page);
  await addNode(page, "image");
  await open(page, "node-image");
  await page.getByTestId("ctx-copy-settings").click();

  await addNode(page, "video");
  await open(page, "node-video");
  await expect(page.getByTestId("ctx-paste-settings")).toBeDisabled();
});

test("right-clicking an unselected block acts on that block, not the old selection", async ({
  page,
}) => {
  // The rule that stops the menu deleting something off-screen: a right-click outside the
  // selection moves the selection to what was clicked.
  await openCanvas(page);
  await addNode(page, "image");
  await addNode(page, "agent");
  await page.getByTestId("node-image").click();
  await expect(page.locator(".react-flow__node.selected")).toHaveCount(1);

  await open(page, "node-agent");
  await page.getByTestId("ctx-delete").click();

  // The Agent went; the Image — which was selected when the menu opened — did not.
  await expect(page.getByTestId("node-agent")).toHaveCount(0);
  await expect(page.getByTestId("node-image")).toHaveCount(1);
});

test("right-clicking inside a multi-selection acts on the whole selection", async ({ page }) => {
  await openCanvas(page);
  await buildChain(page, ["input", "image", "output"]);

  const input = await page.getByTestId("node-input").boundingBox();
  const image = await page.getByTestId("node-image").boundingBox();
  await page.mouse.move(input!.x - 20, input!.y - 20);
  await page.mouse.down();
  await page.mouse.move(image!.x + image!.width + 10, image!.y + image!.height + 10, { steps: 8 });
  await page.mouse.up();
  await expect(page.locator(".react-flow__node.selected")).toHaveCount(2);

  // Right-click the *selection rect*, not the card. React Flow lays that rect over a marquee
  // selection and it swallows the cards' pointer events — so it is what a user's cursor actually
  // hits, and `onSelectionContextMenu` is what has to answer.
  await page.locator(".react-flow__nodesselection-rect").click({ button: "right" });
  // The menu says what it is about to do, rather than leaving the count to be guessed.
  await expect(page.getByTestId("ctx-delete")).toContainText("2 blocks");
  await page.getByTestId("ctx-delete").click();
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
});
