import { expect, test } from "@playwright/test";

// Phase 11 gate (WEEK4-PARTNER-READINESS-PLAN, PR-2): failures are visible. A save that fails
// surfaces an error toast (not just the easy-to-miss inline `saveMsg`). Uses dev sign-in + the
// keyless canvas, and aborts the save request to force the failure — no API key or DB needed.
test("a failed save surfaces an error toast", async ({ page }) => {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.locator(".react-flow__controls")).toBeVisible();

  // Something to save.
  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();

  // Force the save to fail, then save.
  await page.route("**/api/agents", (route) => route.abort());
  await page.getByTestId("save-agent").click();

  const toast = page.getByTestId("toast");
  await expect(toast).toBeVisible();
  await expect(toast).toContainText(/couldn.t save/i);
});
