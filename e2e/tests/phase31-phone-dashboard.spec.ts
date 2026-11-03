import { expect, test } from "@playwright/test";

import { signInAt } from "./helpers";

// The dashboard at phone width (walkthrough, 2026-11-03). The expanded sidebar took 240px of a
// 375px screen, squeezing every page into a strip with the search box drawn over the title. A
// narrow screen now always gets the 60px rail, and no page is wider than the screen.

test.use({ viewport: { width: 375, height: 812 } });

test("a phone gets the icon rail, with no toggle to widen it", async ({ page }) => {
  await signInAt(page, "/dashboard");
  const sidebar = page.locator("aside");
  await expect(sidebar).toHaveAttribute("data-collapsed", "true");
  expect((await sidebar.boundingBox())!.width).toBeLessThanOrEqual(60);
  await expect(page.getByTestId("sidebar-toggle")).toHaveCount(0);
  // Folded, not lost: the destinations are still there, named for screen readers.
  await expect(page.getByTestId("nav-settings")).toHaveAttribute("aria-label", "Settings");
});

for (const path of ["/dashboard", "/dashboard/new", "/dashboard/workflows", "/dashboard/usage", "/dashboard/settings"]) {
  test(`${path} fits a phone without sideways scrolling`, async ({ page }) => {
    await signInAt(page, path);
    await expect(page.locator("main h1")).toBeVisible();
    const main = page.locator("main");
    const { scroll, client } = await main.evaluate((el) => ({
      scroll: el.scrollWidth,
      client: el.clientWidth,
    }));
    expect(scroll).toBeLessThanOrEqual(client);
  });
}
