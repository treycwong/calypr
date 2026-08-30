import { expect, test } from "@playwright/test";

import { addNode, openCanvas } from "./helpers";

/** Answer `/api/workspace` with a plan. The Video block is Plus-only, so a default (free)
 *  workspace can't place one — see `phase23-paid-blocks.spec.ts`, which is where that gate is
 *  actually tested. The real response is passed through with only `plan` overridden. */
async function asPlus(page: import("@playwright/test").Page) {
  await page.route("**/api/workspace", async (route) => {
    const res = await route.fetch();
    const body = await res.json().catch(() => ({}));
    return route.fulfill({ json: { ...body, plan: "plus" } });
  });
}

// The canvas polls the workspace, so a request can still be in the handler when the test ends.
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

// Prompt Instructions live on the Input block: criteria written once, at the entry, that every
// generative block downstream folds into its prompt.
//
// The field is shown only when the graph contains a block that reads it, which is the whole of
// what this spec covers — the engine side (which blocks consume the channel, and which must never
// see it) is `packages/nodes/tests/test_prompt_instructions.py`. What can only be checked here is
// that hiding the control does not *destroy* what was typed into it.

test("the field is absent until the graph has a block that reads it", async ({ page }) => {
  await openCanvas(page);
  await addNode(page, "input");
  await page.getByTestId("node-input").click();

  // A bare Input block has nobody to give instructions to, so the control is not offered.
  await expect(page.getByTestId("cfg-prompt-instructions")).toHaveCount(0);

  await addNode(page, "agent");
  await page.getByTestId("node-input").click();
  // An Agent doesn't read the channel either — the field is for generative media blocks.
  await expect(page.getByTestId("cfg-prompt-instructions")).toHaveCount(0);

  await addNode(page, "image");
  await page.getByTestId("node-input").click();
  await expect(page.getByTestId("cfg-prompt-instructions")).toBeVisible();
});

test("hiding the field does not throw away what was typed in it", async ({ page }) => {
  // The cost of hiding rather than disabling: a user types criteria, deletes the Image block, and
  // has no idea whether their text survived. It does — only the control is conditional, the value
  // stays in the node's config — and this is the test that keeps it that way.
  await asPlus(page);
  await openCanvas(page);
  await addNode(page, "input");
  await addNode(page, "image");

  await page.getByTestId("node-input").click();
  const field = page.getByTestId("cfg-prompt-instructions");
  await field.fill("no text or logos");
  await expect(field).toHaveValue("no text or logos");

  // Remove the only consumer. React Flow deletes the selected node on Backspace.
  await page.getByTestId("node-image").click();
  await page.keyboard.press("Backspace");
  await expect(page.getByTestId("node-image")).toHaveCount(0);

  await page.getByTestId("node-input").click();
  await expect(page.getByTestId("cfg-prompt-instructions")).toHaveCount(0);

  // Put a consumer back: the text is still there.
  await addNode(page, "video");
  await page.getByTestId("node-input").click();
  await expect(page.getByTestId("cfg-prompt-instructions")).toHaveValue("no text or logos");
});

test("the panel names the blocks that will use the instructions", async ({ page }) => {
  await asPlus(page);
  await openCanvas(page);
  await addNode(page, "input");
  await addNode(page, "image");
  await addNode(page, "video");
  await page.getByTestId("node-input").click();

  const panel = page.getByTestId("config-panel");
  await expect(panel).toContainText("Used by: Image, Video");
});
