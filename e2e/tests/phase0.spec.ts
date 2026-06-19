import { expect, test } from "@playwright/test";

import { API_URL } from "../playwright.config";

// Phase 0 gate (CLAUDE-PLAN.md §11): unauthenticated → sign-in; dev sign-in → dashboard;
// API /health ok. Each test runs in a fresh, isolated browser context (no shared cookie).

test("unauthenticated visit to /dashboard redirects to sign-in", async ({ page }) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/sign-in/);
  await expect(page.getByTestId("dev-sign-in")).toBeVisible();
});

test("dev sign-in lands on the dashboard", async ({ page }) => {
  await page.goto("/dashboard"); // proxy bounces to /sign-in?next=/dashboard
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  // The dashboard reflects live API health.
  await expect(page.getByTestId("api-status")).toHaveText(/online/i);
});

test("API /health returns ok", async ({ request }) => {
  const res = await request.get(`${API_URL}/health`);
  expect(res.ok()).toBeTruthy();
  expect((await res.json()).status).toBe("ok");
});
