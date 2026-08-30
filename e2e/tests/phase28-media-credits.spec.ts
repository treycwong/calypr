import { expect, test } from "@playwright/test";

import { addNode, openCanvas } from "./helpers";

// 3D and Video are credit-only — they run on the platform's fal key and there is no BYO path —
// so the config panel says what a run will cost before you spend it. The rate comes from the API
// (`GET /media-prices`), never a copy in the browser, so the number shown is the number charged.

async function asPlus(page: import("@playwright/test").Page) {
  await page.route("**/api/workspace", async (route) => {
    const res = await route.fetch();
    const body = await res.json().catch(() => ({}));
    return route.fulfill({ json: { ...body, plan: "plus" } });
  });
}

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

/** Open the canvas and wait for the paid tile to actually unlock.
 *
 *  The palette locks 3D and Video until the workspace's plan has loaded, so clicking straight
 *  after `openCanvas` races the fetch and opens the upgrade dialog instead of placing a block. */
async function addPaidNode(page: import("@playwright/test").Page, kind: string) {
  await expect(page.getByTestId(`add-${kind}`)).not.toHaveAttribute("data-locked", "true");
  await addNode(page, kind);
}

test("fal is no longer a key a workspace can store", async ({ page }) => {
  // It powered only the 3D and Video blocks, and both are paid for in credits now.
  await openCanvas(page);
  await page.getByTestId("tab-connectors").click();
  await expect(page.getByTestId("key-providers")).toBeVisible();
  await expect(page.getByTestId("key-provider-fal")).toHaveCount(0);
  // The keys that still do something are untouched.
  await expect(page.getByTestId("key-provider-openai")).toBeVisible();
});

test("the Video block quotes its cost, and it tracks every knob that moves it", async ({
  page,
}) => {
  await asPlus(page);
  await openCanvas(page);
  await addPaidNode(page, "video");
  await page.getByTestId("node-video").click();

  const estimate = page.getByTestId("credit-estimate");
  // Seedance 1.0, 720p, 5s.
  await expect(estimate).toContainText("54 credits");

  // The expensive tier is ~10x per second — the number this whole feature exists to surface.
  await page.getByTestId("cfg-model").selectOption("bytedance/seedance-2.0/fast/text-to-video");
  await expect(estimate).toContainText("605 credits");

  // Length multiplies it: ten seconds on that tier is over half a monthly grant.
  await page.getByTestId("cfg-duration").selectOption("10");
  await expect(estimate).toContainText("1,209 credits");

  // Resolution roughly halves it.
  await page.getByTestId("cfg-resolution").selectOption("480p");
  await expect(estimate).toContainText("538 credits");
});

test("an unpriced model shows no estimate rather than a wrong one", async ({ page }) => {
  // `fake` is free and keyless. A guessed number here would cost real credits to be wrong about.
  await asPlus(page);
  await openCanvas(page);
  await addPaidNode(page, "video");
  await page.getByTestId("node-video").click();
  await page.getByTestId("cfg-model").selectOption("fake");
  await expect(page.getByTestId("credit-estimate")).toHaveCount(0);
});

test("the 3D block quotes its cost per generation", async ({ page }) => {
  await asPlus(page);
  await openCanvas(page);
  await addPaidNode(page, "mesh");
  await page.getByTestId("node-mesh").click();
  // A mesh bills per generation, so there is no length to multiply by.
  await expect(page.getByTestId("credit-estimate")).toContainText("10 credits");
});
