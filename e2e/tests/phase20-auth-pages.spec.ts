import { expect, test } from "@playwright/test";

import { waitForHydration } from "./helpers";

// `/sign-up` is mechanically the same page as `/sign-in` — social sign-in creates the user on
// first use — so what's worth asserting is that the two are distinguishable to a visitor and
// that the new route is a real, working entry point rather than a decorative alias.
//
// These run on the dev-auth path (no BETTER_AUTH_SECRET in CI), so the provider buttons aren't
// rendered; `dev-sign-in` stands in for them, exactly as on `/sign-in`.

test("sign-up renders its own heading, not the log-in one", async ({ page }) => {
  await page.goto("/sign-up");
  await expect(page.getByRole("heading", { name: "Create your Calypr account" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Log in to Calypr" })).toHaveCount(0);
});

test("sign-up signs you in and lands on the dashboard", async ({ page }) => {
  await page.goto("/sign-up");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/dashboard/);
});

test("the two auth pages link to each other", async ({ page }) => {
  await page.goto("/sign-in");
  await expect(page.getByRole("heading", { name: "Log in to Calypr" })).toBeVisible();
  // Unlike `dev-sign-in` — a form post that lands whether or not React is up — these are Next
  // `<Link>`s, and a click before hydration is dropped. See `waitForHydration`.
  await waitForHydration(page);
  await page.getByRole("link", { name: "Create an account" }).click();
  await expect(page).toHaveURL(/\/sign-up/);
  await waitForHydration(page);
  await page.getByRole("link", { name: "Log in", exact: true }).click();
  await expect(page).toHaveURL(/\/sign-in/);
});

// The decorative WebGL backdrop must never be load-bearing: headless Chromium may have no GPU,
// and the card is clicked the instant the HTML lands.
test("the backdrop does not block or delay the sign-in card", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/sign-in");
  await expect(page.getByTestId("dev-sign-in")).toBeVisible();
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/dashboard/);
  expect(errors).toEqual([]);
});
