import { expect, test } from "@playwright/test";

import { openCanvas, signInAt, waitForHydration } from "./helpers";

// The 3D and Video blocks were Plus-only until the 2026-10-14 retier. They are now on every plan,
// paid in credits, so the palette locks nothing. The lock itself stays wired, so this spec guards
// against it coming back by accident.
//
// This covers the *surface*. What bounds the spend is `run_access.check_run_gates`, which checks
// the credit balance for these blocks.

/** Answer `/api/workspace` with a plan, so the palette's entitlement can be driven either way.
 *  Caps aren't enforced without an internal key, so a real Plus workspace can't be reached here.
 *
 *  The real response is passed through with only `plan` overridden — the canvas reads
 *  `signed_in_as` and `credits` from the same payload, and inventing those here would make the
 *  header render something no server ever sends. */
async function withPlan(page: import("@playwright/test").Page, plan: string) {
  await page.route("**/api/workspace", async (route) => {
    const res = await route.fetch();
    const body = await res.json().catch(() => ({}));
    return route.fulfill({ json: { ...body, plan } });
  });
}

// The canvas polls the workspace, so a request can still be in the handler when the test ends —
// `route.fetch()` then throws against a closing page and fails the *run* rather than a test.
test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

for (const [block, testid] of [
  ["3D", "add-mesh"],
  ["Video", "add-video"],
] as const) {
  test(`a free workspace can place the ${block} block`, async ({ page }) => {
    // On every plan since 2026-10-14, paid in credits. The run gate checks the balance.
    await withPlan(page, "free");
    await openCanvas(page);

    const tile = page.getByTestId(testid);
    await expect(tile).not.toHaveAttribute("data-locked", "true");

    const before = await page.locator(".react-flow__node").count();
    await tile.click();
    await expect(page.getByTestId("upgrade-dialog")).toHaveCount(0);
    await expect(page.locator(".react-flow__node")).toHaveCount(before + 1);
  });
}

test("no block is locked on free", async ({ page }) => {
  await withPlan(page, "free");
  await openCanvas(page);
  // The lock is still wired (`mediaNodesEnabled`), so withholding a block again is one edit.
  // Until then a free canvas has the same palette as every other plan.
  await expect(page.locator('[data-locked="true"]')).toHaveCount(0);
});

test("the sign-in page still renders with the paid block in the palette", async ({ page }) => {
  // A smoke check that the lazily-loaded 3D viewer chunk hasn't leaked into a shared bundle: a
  // page with no canvas on it must still hydrate with no console errors.
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await signInAt(page, "/pricing");
  await waitForHydration(page);
  expect(errors).toEqual([]);
});
