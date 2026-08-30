import { expect, test } from "@playwright/test";

import { openCanvas } from "./helpers";

// The fal key is only spendable by the 3D and Video blocks, and both are Plus-only — so on Free
// the field is somewhere to paste a credential that can never be used. The list is filtered by
// the API, not by the browser: the panel renders whatever `GET /provider-keys` returns.

async function withPlan(page: import("@playwright/test").Page, plan: string) {
  await page.route("**/api/workspace", async (route) => {
    const res = await route.fetch();
    const body = await res.json().catch(() => ({}));
    return route.fulfill({ json: { ...body, plan } });
  });
}

/** Answer the provider list the way the API would for a plan, so the panel can be checked without
 *  a real subscription — the server-side rule itself is covered in `test_entitlements.py`. */
async function withProviders(page: import("@playwright/test").Page, providers: string[]) {
  await page.route("**/api/provider-keys", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      json: providers.map((provider) => ({ provider, has_key: false, key_hint: null })),
    });
  });
}

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

const openKeys = async (page: import("@playwright/test").Page) => {
  await openCanvas(page);
  await page.getByTestId("tab-connectors").click();
  await expect(page.getByTestId("key-providers")).toBeVisible();
};

test("a free workspace is not offered the fal key", async ({ page }) => {
  await withPlan(page, "free");
  await withProviders(page, ["openai", "anthropic", "tavily", "unsplash"]);
  await openKeys(page);

  await expect(page.getByTestId("key-provider-fal")).toHaveCount(0);
  // The others are untouched — this is one provider, not a general lockdown.
  await expect(page.getByTestId("key-provider-openai")).toBeVisible();
  await expect(page.getByTestId("key-provider-unsplash")).toBeVisible();
});

test("a plus workspace is offered it", async ({ page }) => {
  await withPlan(page, "plus");
  await withProviders(page, ["openai", "anthropic", "tavily", "unsplash", "fal"]);
  await openKeys(page);

  await expect(page.getByTestId("key-provider-fal")).toBeVisible();
});

test("the grid follows the API, not a list in the browser", async ({ page }) => {
  // The bug this fixes: the panel iterated a hardcoded map and rendered `fal` regardless of what
  // the server said. `moonshot` must still stay out — it is managed in Dashboard → Settings, and
  // it is excluded by having no label here rather than by the plan.
  await withProviders(page, ["openai", "moonshot", "fal"]);
  await openKeys(page);

  await expect(page.getByTestId("key-provider-openai")).toBeVisible();
  await expect(page.getByTestId("key-provider-fal")).toBeVisible();
  await expect(page.getByTestId("key-provider-moonshot")).toHaveCount(0);
  await expect(page.getByTestId("key-provider-tavily")).toHaveCount(0);
});
