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

test("checkout is honest that it cannot take a card yet", async ({ page }) => {
  // The thing that must not regress once Stripe lands: no card fields, no implication of one.
  await page.goto("/checkout?plan=plus");

  await expect(page.getByTestId("checkout-pending")).toContainText("Card payments open shortly");
  await expect(page.locator('input[name="cardnumber"]')).toHaveCount(0);
  await expect(page.getByTestId("checkout-notify")).toBeVisible();
});

test("checkout captures intent", async ({ page }) => {
  await page.goto("/checkout?plan=plus");

  await page.getByTestId("checkout-email").fill("buyer@example.com");
  await page.getByTestId("checkout-notify").click();
  await expect(page.getByTestId("checkout-done")).toContainText("buyer@example.com");
});
