import { expect, test } from "@playwright/test";

// The public marketing landing at `/` renders, and its CTAs route into the (gated) app.

test("the landing page renders the hero and CTAs", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /Design AI agents visually/i }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Open the canvas" }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Sign in" }).first()).toBeVisible();
  // the agent-ladder templates are showcased
  await expect(page.getByText("Reflexion", { exact: true })).toBeVisible();
});

test("an unauthenticated CTA into the app hits the auth gate", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Open canvas" }).click(); // nav CTA → /canvas
  await expect(page).toHaveURL(/\/sign-in/);
  await expect(page.getByTestId("dev-sign-in")).toBeVisible();
});
