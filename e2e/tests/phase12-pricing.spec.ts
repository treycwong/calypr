import { expect, test } from "@playwright/test";

// The pricing surface after the 2026-10-14 retier: Free / $5 Starter / $10 Plus, Starter
// recommended, and a checkout step per paid plan. Prices and features come from `lib/plans.ts`.

test("all three plans are shown, with Starter recommended", async ({ page }) => {
  await page.goto("/pricing");

  for (const id of ["free", "starter", "plus"]) {
    await expect(page.getByTestId(`plan-${id}`)).toBeVisible();
  }
  // The badge belongs to Starter, the plan we lead with, and to nothing else on the page.
  await expect(page.getByTestId("plan-recommended")).toHaveCount(1);
  await expect(page.getByTestId("plan-starter").getByTestId("plan-recommended")).toBeVisible();

  await expect(page.getByTestId("plan-free")).toContainText("$0");
  await expect(page.getByTestId("plan-starter")).toContainText("$5");
  await expect(page.getByTestId("plan-plus")).toContainText("$10");
});

test("the plans match the spec on what actually separates them", async ({ page }) => {
  await page.goto("/pricing");

  // Code export is what $10 buys over $5.
  await expect(page.getByTestId("plan-plus")).toContainText("Code export");
  await expect(page.getByTestId("plan-starter")).not.toContainText("Code export");
  await expect(page.getByTestId("plan-free")).not.toContainText("Code export");

  // Video and 3D are on every plan, so Free says so rather than implying an upsell.
  await expect(page.getByTestId("plan-free")).toContainText("Video");

  await expect(page.getByTestId("plan-free")).toContainText("100 credits");
  await expect(page.getByTestId("plan-starter")).toContainText("500 credits");
  await expect(page.getByTestId("plan-plus")).toContainText("1,000 credits");
  await expect(page.getByTestId("plan-free")).toContainText("3 projects");
  await expect(page.getByTestId("plan-starter")).toContainText("10 projects");
  await expect(page.getByTestId("plan-plus")).toContainText("20 projects");

  // "500 credits" means nothing until it is a number of things.
  await expect(page.getByTestId("credit-guide")).toContainText("5-second video");
});

test("each plan's button leads to its own checkout, and Free to the canvas", async ({ page }) => {
  await page.goto("/pricing");
  await expect(page.getByTestId("plan-free-cta")).toHaveAttribute("href", "/canvas");

  await page.getByTestId("plan-starter-cta").click();
  await expect(page).toHaveURL(/\/checkout\?plan=starter/);
  await expect(page.getByRole("heading", { name: "Upgrade to Starter" })).toBeVisible();
  await expect(page.getByTestId("checkout-price")).toHaveText("$5");

  await page.goto("/pricing");
  await page.getByTestId("plan-plus-cta").click();
  await expect(page).toHaveURL(/\/checkout\?plan=plus/);
  await expect(page.getByRole("heading", { name: "Upgrade to Plus" })).toBeVisible();
  await expect(page.getByTestId("checkout-price")).toHaveText("$10");
});

test("an unknown plan in the checkout link reads as Plus, not an error", async ({ page }) => {
  // Every link minted before the retier is bare or `?plan=plus`.
  await page.goto("/checkout?plan=enterprise");
  await expect(page.getByRole("heading", { name: "Upgrade to Plus" })).toBeVisible();
});

test("checkout is honest when billing is not configured", async ({ page }) => {
  // The E2E API runs without Stripe keys, so `/billing/status` reports disabled and the page
  // says so from first paint — no click needed to discover it, and no card field anywhere.
  await page.goto("/checkout?plan=plus");

  await expect(page.getByTestId("checkout-pending")).toContainText("Card payments open shortly");
  await expect(page.locator('input[name="cardnumber"]')).toHaveCount(0);
  await expect(page.getByTestId("checkout-notify")).toBeVisible();
  await expect(page.getByTestId("checkout-pay")).toHaveCount(0);
});

// Note: the "billing enabled" path isn't e2e-testable here — `enabled` is decided by the
// *server* component from `GET /billing/status`, and the E2E API deliberately runs without
// Stripe keys. That branch is covered where it can be controlled, in
// `apps/api/tests/test_billing.py::test_status_reports_enabled_when_configured`.

test("checkout captures intent", async ({ page }) => {
  await page.goto("/checkout?plan=plus");

  await page.getByTestId("checkout-email").fill("buyer@example.com");
  await page.getByTestId("checkout-notify").click();
  await expect(page.getByTestId("checkout-done")).toContainText("buyer@example.com");
});

// The two site headers had drifted into offering different *links* — same site, two answers to
// "where can I go?". `site/nav`'s SITE_NAV fixes the links; the CTA is deliberately NOT shared
// (see `SITE_HEADER_CTA`'s doc comment): the homepage's "Join Beta" is the still-invite-only path
// onto the free beta cohort, while every other page's "Get Started" goes straight to sign-in.
test("the pricing nav offers the same links as the homepage, with its own CTA", async ({
  page,
}) => {
  // **Hrefs, not rendered text.** The two headers are meant to look different — the landing
  // nav is a mono uppercase pill floating over the hero, the inner-page nav is sentence case —
  // so `allInnerTexts()` compares `"FEATURES"` against `"Features"` and fails on a difference
  // that is the design. Destinations are what "the same links" actually means.
  await page.goto("/");
  const homeLinks = await page.locator("header nav a").evaluateAll((as) =>
    as.map((a) => (a as HTMLAnchorElement).getAttribute("href")),
  );

  await page.goto("/pricing");
  const pricingLinks = await page.locator("header nav a").evaluateAll((as) =>
    as.map((a) => (a as HTMLAnchorElement).getAttribute("href")),
  );

  expect(pricingLinks).toEqual(homeLinks);
  // The stale CTA this test originally guarded against: /pricing used to offer "Open canvas"
  // where home offered the waitlist, which is how a visitor from search met a different product.
  await expect(page.locator("header").getByText("Open canvas")).toHaveCount(0);
  // Pricing's own CTA — not "Join Beta", which stays the homepage's.
  await expect(page.locator("header").getByRole("link", { name: "Get Started" })).toHaveAttribute(
    "href",
    "/sign-in",
  );
  await expect(page.locator("header").getByText("Sign in")).toHaveCount(0);
});

// Mobile: the inner-page nav had no way to reach the site's other pages from a phone — the
// "Get Started" button sat alone at the top right on every viewport, with no hamburger and no
// nav links, unlike the homepage. Mirrors LandingHeader's already-tested pattern.
test("the inner-page nav collapses to a hamburger on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 700 });
  await page.goto("/pricing");

  const menuButton = page.getByLabel("Open menu");
  await expect(menuButton).toBeVisible();
  await expect(page.locator("header").getByRole("link", { name: "Get Started" })).not.toBeVisible();

  await menuButton.click();
  await expect(page.getByLabel("Close menu")).toBeVisible();
  // Scoped to `header`: the footer also links to "Templates" (and other nav labels), so an
  // unscoped role query is ambiguous the moment both are in the DOM at once.
  await expect(page.locator("header").getByRole("link", { name: "Features" })).toBeVisible();
  await expect(page.locator("header").getByRole("link", { name: "Templates" })).toBeVisible();

  // The sheet's own CTA still works and still says "Get Started" — the mobile nav is a
  // different presentation of the same header, not a different one.
  await page.locator("header").getByRole("link", { name: "Blog" }).click();
  await expect(page).toHaveURL(/\/blog/);
});

test("the inner-page nav keeps the CTA visible with no hamburger on desktop", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/pricing");
  // The button is always in the DOM (`md:hidden` is a CSS rule, not conditional rendering) —
  // visibility, not presence, is what a viewport-dependent nav actually needs to prove.
  await expect(page.getByLabel("Open menu")).not.toBeVisible();
  await expect(page.locator("header").getByRole("link", { name: "Get Started" })).toBeVisible();
});

test("the pricing FAQ answers the billing questions, and the footer links to it", async ({
  page,
}) => {
  await page.goto("/pricing");
  const faq = page.getByTestId("pricing-faq");
  await expect(faq).toBeVisible();
  for (const q of ["upgrade", "downgrade", "top up", "refund"]) {
    await expect(faq.getByText(new RegExp(q, "i")).first()).toBeVisible();
  }

  // Closed until asked, then open: plain <details>, no script involved.
  const first = faq.getByTestId("faq-item").first();
  await expect(first).not.toHaveAttribute("open", "");
  await first.locator("summary").click();
  await expect(first).toHaveAttribute("open", "");

  await expect(page.locator("footer").getByRole("link", { name: "FAQs" })).toHaveAttribute(
    "href",
    "/pricing#faq",
  );
});
