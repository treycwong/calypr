import { expect, type Page, test } from "@playwright/test";

// Phase 4 gate: the agent ladder + conditional control flow reach the canvas and project to
// ownable Python. A Reflection agent emits its critique→revise loop, and an If-Else router
// emits `add_conditional_edges`. Viewing code needs no API key and no database.

async function openCanvas(page: Page) {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  // Wait until React Flow has mounted client-side so the palette handlers are wired.
  await expect(page.locator(".react-flow__controls")).toBeVisible();
}

test("an If-Else router projects to add_conditional_edges", async ({ page }) => {
  await openCanvas(page);

  // Input → If-Else → Output; the auto-linked router edge carries its default branch.
  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-router").click();
  await expect(page.getByTestId("node-router")).toBeVisible();
  await page.getByTestId("add-output").click();
  await expect(page.getByTestId("node-output")).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  await expect(code).toContainText("add_conditional_edges");
});

test("a starter template loads onto the canvas and projects to code", async ({
  page,
}) => {
  await openCanvas(page);

  // Loading an archetype hydrates the canvas from its GraphSpec (API → proxy → canvas).
  await page.getByTestId("template-picker").selectOption({ label: "Reflection" });
  await expect(page.getByTestId("node-agent")).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("critique_prompt", { timeout: 15_000 });
});
