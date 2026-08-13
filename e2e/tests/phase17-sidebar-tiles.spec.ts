import { expect, test } from "@playwright/test";

import { openCanvas } from "./helpers";

// The sidebar panels became weavy-style tile grids: monochrome icon over a label, with a hover
// card carrying the full name and a sentence of description. Clicking still does what it did —
// phase5 and friends cover that through `add-*` and the template names — so these cover the
// tiles' own behaviour: that the card appears on a longer hover, and that the two template
// groups are named for what separates them.

test("a block tile explains itself on a longer hover", async ({ page }) => {
  await openCanvas(page);

  const card = page.getByText("Retrieval-augmented generation", { exact: false });
  await expect(card).toHaveCount(0);

  await page.getByTestId("add-retriever").hover();

  // Base UI's default 600ms open delay: the card must not flash while the pointer is merely
  // crossing the grid, so this deliberately waits rather than asserting immediately.
  await expect(card).toBeVisible({ timeout: 5_000 });
  // The card names the block as well as describing it.
  await expect(page.getByText("Knowledge", { exact: true }).last()).toBeVisible();
});

test("the hover card does not block the click", async ({ page }) => {
  await openCanvas(page);

  // The tile *is* the tooltip trigger rather than a wrapper, so hovering long enough to open the
  // card and then clicking still adds the node.
  await page.getByTestId("add-agent").hover();
  await expect(page.getByText("An LLM step", { exact: false })).toBeVisible({ timeout: 5_000 });
  await page.getByTestId("add-agent").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();
});

test("templates are grouped into Frameworks and Workflows", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("tab-templates").click();

  const panel = page.getByTestId("templates-panel");
  await expect(panel.getByText("Frameworks", { exact: true })).toBeVisible();
  await expect(panel.getByText("Workflows", { exact: true })).toBeVisible();
  // The group that holds the use-case systems is no longer called "Templates" — that was the
  // name of the panel containing it, so it said nothing.
  await expect(panel.getByText("Templates", { exact: true })).toHaveCount(0);

  // A workflow tile still carries its full name as its accessible name, which is how the other
  // specs select templates.
  await expect(
    panel.getByRole("button", { name: "Market research report", exact: true }),
  ).toBeVisible();
});
