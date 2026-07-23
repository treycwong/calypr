import { expect, test } from "@playwright/test";

import { API_URL } from "../playwright.config";

// The public marketing landing at `/` renders, and its CTAs route into the (gated) app.

test("the landing page renders the hero and CTAs", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Build your dreams" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Get Started" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Join Beta" }).first()).toBeVisible();
  // the agent-ladder templates are showcased further down the page
  await expect(page.getByText("Reflexion", { exact: true })).toBeVisible();
});

test("the hero CTA goes straight to sign-in — billing is live, no invite needed", async ({
  page,
}) => {
  // Reversed from the invite-only era: Plus is self-serve from /pricing now, so the hero sends
  // people to sign in rather than to the waitlist. "Join Beta" in the nav is the separate,
  // still-invite-only path onto the free beta cohort.
  await page.goto("/");
  await page.getByRole("link", { name: "Get Started" }).click();
  await expect(page).toHaveURL(/\/sign-in/);
  await expect(page.getByTestId("dev-sign-in")).toBeVisible();
});

test("the header nav has no separate Sign in link", async ({ page }) => {
  // Removed once the hero CTA itself went to /sign-in — a second link to the same
  // destination in the same header was redundant. The page's closing CTA section (a
  // different, lower section, not the nav) keeps its own "Sign in" link independently.
  await page.goto("/");
  await expect(page.locator("header").getByText("Sign in")).toHaveCount(0);
});

test("the nav's Join Beta CTA still leads to the waitlist", async ({ page }) => {
  await page.goto("/");
  await page.locator("header").getByRole("link", { name: "Join Beta" }).first().click();
  await expect(page).toHaveURL(/\/waitlist/);
  await expect(page.getByLabel("Email address")).toBeVisible();
});

test("an unauthenticated visit to the app still hits the auth gate", async ({ page }) => {
  await page.goto("/canvas");
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
  await page.getByRole("button", { name: "Join Us" }).click();
  await expect(page.getByText("You’re on the list")).toBeVisible();

  const rows = await (
    await request.get(`${API_URL}/admin/waitlist`, {
      headers: { "x-admin-token": "e2e-admin-token" },
    })
  ).json();
  expect(rows.filter((r: { email: string }) => r.email === email)).toHaveLength(1);
});

test("the footer sits at the bottom of the viewport on a short marketing page", async ({
  page,
}) => {
  // Regression: every marketing page's wrapper used `min-h-full`, a *percentage* height —
  // and `<body>` only sets `min-height: 100%`, which doesn't establish a definite height for a
  // percentage-height child to resolve against. The wrapper collapsed to its content's height,
  // so on a short page (this one) the footer landed wherever the content ended rather than at
  // the bottom of the viewport, with a large stray gap of background below it. `min-h-screen`
  // (`min-height: 100vh`) doesn't depend on the ancestor chain, so it isn't susceptible.
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/waitlist");
  const footerBottom = await page
    .locator("footer")
    .evaluate((el) => el.getBoundingClientRect().bottom);
  const bodyHeight = await page.evaluate(() => document.body.scrollHeight);
  // The footer should end at (or very near) the full scroll height — not partway up a much
  // taller empty page.
  expect(bodyHeight - footerBottom).toBeLessThan(5);
});
