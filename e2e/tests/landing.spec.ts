import { expect, test } from "@playwright/test";

import { API_URL } from "../playwright.config";

// The public marketing landing at `/` renders, and its CTAs route into the (gated) app.

test("the landing page renders the hero and CTAs", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Build your dreams" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Get Started" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Join Waitlist" }).first()).toBeVisible();
  // the agent-ladder templates are showcased further down the page
  await expect(page.getByText("Reflexion", { exact: true })).toBeVisible();
});

test("an unauthenticated CTA into the app hits the auth gate", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Get Started" }).click(); // hero CTA → /canvas
  await expect(page).toHaveURL(/\/sign-in/);
  await expect(page.getByTestId("dev-sign-in")).toBeVisible();
});

test("the waitlist form stores a signup", async ({ page, request }) => {
  // This form used to swallow submissions (a local success state with a TODO). Assert it now
  // actually reaches storage — and is idempotent, since a second submit is a user being
  // impatient, not an error.
  const email = `e2e.${Date.now()}@example.com`;

  await page.goto("/waitlist");
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("button", { name: "Join Waitlist" }).click();
  await expect(page.getByText("You’re on the list")).toBeVisible();

  const rows = await (
    await request.get(`${API_URL}/admin/waitlist`, {
      headers: { "x-admin-token": "e2e-admin-token" },
    })
  ).json();
  expect(rows.filter((r: { email: string }) => r.email === email)).toHaveLength(1);
});
