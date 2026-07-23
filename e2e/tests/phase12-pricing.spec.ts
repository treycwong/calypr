import { expect, test } from "@playwright/test";

// The pricing surface: two plans, Plus recommended, and a checkout step that Stripe will take
// over in Week 9. Until it does, the page must not imply it can take a card.

test("both plans are shown, with Plus recommended", async ({ page }) => {
  await page.goto("/pricing");

  await expect(page.getByTestId("plan-free")).toBeVisible();
  await expect(page.getByTestId("plan-plus")).toBeVisible();
  await expect(page.getByTestId("plan-recommended")).toBeVisible();
  // The badge belongs to Plus, not just anywhere on the page.
  await expect(page.getByTestId("plan-plus").getByTestId("plan-recommended")).toBeVisible();

  await expect(page.getByTestId("plan-free")).toContainText("$0");
  await expect(page.getByTestId("plan-plus")).toContainText("$20");
});

test("the plans match the spec on what actually separates them", async ({ page }) => {
  await page.goto("/pricing");

  // Code export is the one non-capacity difference, and the reason Plus exists at all.
  await expect(page.getByTestId("plan-plus")).toContainText("Code export");
  await expect(page.getByTestId("plan-free")).not.toContainText("Code export");

  await expect(page.getByTestId("plan-free")).toContainText("3 projects");
  await expect(page.getByTestId("plan-plus")).toContainText("20 projects");
  await expect(page.getByTestId("plan-plus")).toContainText("2,000 credits");
});

test("Select plan leads to checkout, and Free leads to the canvas", async ({ page }) => {
  await page.goto("/pricing");

  await expect(page.getByTestId("plan-free-cta")).toHaveAttribute("href", "/canvas");

  await page.getByTestId("plan-plus-cta").click();
  await expect(page).toHaveURL(/\/checkout/);
  await expect(page.getByRole("heading", { name: "Upgrade to Plus" })).toBeVisible();
  await expect(page.getByText("$20")).toBeVisible();
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
  await page.goto("/");
  const homeLinks = await page.locator("header nav a").allInnerTexts();

  await page.goto("/pricing");
  const pricingLinks = await page.locator("header nav a").allInnerTexts();

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
