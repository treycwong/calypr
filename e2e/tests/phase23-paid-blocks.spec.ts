import { expect, test } from "@playwright/test";

import { openCanvas, signInAt, waitForHydration } from "./helpers";

// The 3D block is Plus-only, and the palette says so rather than hiding it. A block nobody can
// discover sells nothing, and hiding it would make the canvas silently different per plan — so
// someone opening a shared graph or the "Image to 3D" template would meet a block that doesn't
// exist in their own sidebar.
//
// This covers the *surface*. The paywall itself is `run_access.check_run_gates`, which refuses the
// run with a `plan_required` code whoever's key would have paid for it — a client-side lock is not
// a paywall, and this spec is not what stops a free account generating meshes.

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

test("a free workspace sees the 3D block locked, and cannot place it", async ({ page }) => {
  await withPlan(page, "free");
  await openCanvas(page);

  const tile = page.getByTestId("add-mesh");
  await expect(tile).toBeVisible();
  await expect(tile).toHaveAttribute("data-locked", "true");
  // Not draggable: dropping it on the canvas would build a graph that only fails at Run.
  await expect(tile).toHaveJSProperty("draggable", false);

  const before = await page.locator(".react-flow__node").count();
  await tile.click();

  const dialog = page.getByTestId("upgrade-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText("3D block is part of Plus");
  await expect(dialog).toContainText("3D blocks");
  await expect(page.getByTestId("upgrade-cta")).toHaveAttribute("href", "/checkout?plan=plus");

  // The refusal is the whole point: no node lands on the canvas.
  expect(await page.locator(".react-flow__node").count()).toBe(before);
});

test("a plus workspace can place the 3D block", async ({ page }) => {
  await withPlan(page, "plus");
  await openCanvas(page);

  const tile = page.getByTestId("add-mesh");
  await expect(tile).not.toHaveAttribute("data-locked", "true");

  const before = await page.locator(".react-flow__node").count();
  await tile.click();
  await expect(page.getByTestId("upgrade-dialog")).toHaveCount(0);
  await expect(page.locator(".react-flow__node")).toHaveCount(before + 1);
});

test("every other block stays unlocked on free", async ({ page }) => {
  await withPlan(page, "free");
  await openCanvas(page);
  // The gate is an allowlist of paid types, not a general filter — if it ever widened, this is
  // where a free canvas quietly losing its blocks would show up.
  await expect(page.locator('[data-locked="true"]')).toHaveCount(1);
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
