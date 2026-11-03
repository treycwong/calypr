import { expect, test } from "@playwright/test";

import { API_URL } from "../playwright.config";

// The public marketing landing at `/` renders, and its CTAs route into the (gated) app.

test("the landing page renders the hero and CTAs", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Craft your next agentic app" })).toBeVisible();
  await expect(page.getByTestId("hero-cta")).toBeVisible();
  await expect(page.locator("header").getByRole("link", { name: "Get Started" })).toBeVisible();
  // The beta is over: the canvas is open, so nothing on the page should still queue people up.
  await expect(page.getByRole("link", { name: "Join Beta" })).toHaveCount(0);
  // the agent-ladder templates are showcased further down the page
  await expect(page.getByText("Reflexion", { exact: true })).toBeVisible();
});

test("the hero CTA goes to sign-up, not to a log-in page that says welcome back", async ({
  page,
}) => {
  // Whoever clicks "Get Started" is new. /sign-in greets them with "Welcome back", which is
  // how this used to read to a first-time visitor.
  await page.goto("/");
  await page.getByTestId("hero-cta").click();
  await expect(page).toHaveURL(/\/sign-up/);
  await expect(page.getByTestId("dev-sign-in")).toBeVisible();
});

test("the header nav has no separate Sign in link", async ({ page }) => {
  // Removed once the hero CTA itself went to the auth pages — a second link to the same
  // destination in the same header was redundant.
  await page.goto("/");
  await expect(page.locator("header").getByText("Sign in")).toHaveCount(0);
});

test("the homepage header offers Get Started, same as every other page", async ({ page }) => {
  // It used to offer "Join Beta" onto an invite-only waitlist, after billing went live.
  await page.goto("/");
  await expect(page.locator("header").getByRole("link", { name: "Get Started" })).toHaveAttribute(
    "href",
    "/sign-up",
  );
});

test("the footer has no dead links", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator('footer a[href="#"]')).toHaveCount(0);
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
  await page.getByRole("button", { name: "Get updates" }).click();
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

test("the waitlist form's input and button share the same height", async ({ page }) => {
  // Regression: the input's height came from `py-2` padding and the button from a fixed `h-8`
  // (later `h-9`) — implicit vs. explicit sizing that had already drifted apart once. Assert
  // the actual rendered box heights match rather than trusting the class names to agree.
  await page.goto("/waitlist");
  const inputHeight = await page
    .getByLabel("Email address")
    .evaluate((el) => el.getBoundingClientRect().height);
  const buttonHeight = await page
    .getByRole("button", { name: "Get updates" })
    .evaluate((el) => el.getBoundingClientRect().height);
  expect(Math.abs(inputHeight - buttonHeight)).toBeLessThan(1);
});
