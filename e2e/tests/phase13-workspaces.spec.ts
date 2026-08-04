import { expect, test } from "@playwright/test";

import { signInAt } from "./helpers";

// The workspace switcher in the sidebar header.
//
// **The workspace list can't be mocked from the browser.** The dashboard layout is a server
// component that fetches it from the Python API directly (`lib/api-server.ts`) so the workspace
// name is right on first paint — `page.route` never sees that request. So these assert against
// whatever the real API returns and never hard-code an id. What *is* mockable is everything the
// client does: creating a workspace and setting the cookie.
//
// Under e2e there is also no `CALYPR_INTERNAL_KEY` guarantee either way, and the caps are the
// API's job regardless — enforcement is covered by `apps/api/tests/test_accounts.py`, which can
// set a plan. These cover the UI: that the list renders, that a create posts and switches, and
// that a cap answer is shown in place rather than thrown.

async function signIn(page: import("@playwright/test").Page) {
  await signInAt(page, "/dashboard");
  await expect(page.getByTestId("ws-switcher")).toBeVisible();
}

test("the switcher lists the account's workspaces and marks the current one", async ({ page }) => {
  await signIn(page);
  await page.getByTestId("ws-switcher").click();

  // At least the current workspace, whatever it is called.
  const options = page.locator('[data-testid^="ws-option-"]');
  await expect(options.first()).toBeVisible();
  expect(await options.count()).toBeGreaterThan(0);

  // The switcher header shows the same workspace the menu marks as current.
  const currentName = (await options.first().textContent())?.trim();
  await expect(page.getByTestId("ws-switcher")).toContainText(currentName ?? "");

  await expect(page.getByTestId("ws-new")).toBeVisible();
});

test("creating a workspace posts the name and switches to it", async ({ page }) => {
  let postedName: string | null = null;
  let switchedTo: string | null = null;
  const created = "11111111-1111-1111-1111-111111111111";

  await page.route("**/api/workspaces", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    postedName = JSON.parse(route.request().postData() ?? "{}").name;
    return route.fulfill({ json: { id: created, name: postedName } });
  });
  await page.route("**/api/workspace/switch", async (route) => {
    switchedTo = JSON.parse(route.request().postData() ?? "{}").workspace_id || null;
    await route.fulfill({ status: 204, body: "" });
  });

  await signIn(page);
  await page.getByTestId("ws-switcher").click();
  await page.getByTestId("ws-new").click();
  await page.getByTestId("ws-new-name").fill("Side project");
  await page.getByTestId("ws-new-submit").click();

  await expect.poll(() => postedName).toBe("Side project");
  // Creating one and then having to go find it would be a strange thing to make someone do.
  await expect.poll(() => switchedTo).toBe(created);
});

test("hitting the workspace cap is answered in place, not thrown", async ({ page }) => {
  // The 402 is an expected answer — someone on Free who clicks "New workspace" should read what
  // they ran out of and where to go, not a generic failure.
  await page.route("**/api/workspaces", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    return route.fulfill({
      status: 402,
      json: {
        detail: {
          reason: "workspace_cap",
          limit: 1,
          used: 1,
          plan: "free",
          message: "You've used 1 of 1 workspace on Free.",
        },
      },
    });
  });

  await signIn(page);
  await page.getByTestId("ws-switcher").click();
  await page.getByTestId("ws-new").click();
  await page.getByTestId("ws-new-name").fill("Second");
  await page.getByTestId("ws-new-submit").click();

  const error = page.getByTestId("ws-new-error");
  await expect(error).toContainText("1 of 1 workspace on Free");
  await expect(error.getByRole("link", { name: "See plans" })).toBeVisible();
  // Still open, so they can change their mind rather than lose what they typed.
  await expect(page.getByTestId("ws-new-name")).toBeVisible();
});

test("Templates and Usage are reachable from the sidebar", async ({ page }) => {
  await signIn(page);

  await page.getByTestId("nav-templates").click();
  await expect(page.getByTestId("templates-empty")).toBeVisible();

  await page.getByTestId("nav-usage").click();
  await expect(page.getByRole("heading", { name: "Usage" })).toBeVisible();
  // The three account-level rows that moved here from Settings.
  await expect(page.getByTestId("usage-projects")).toBeVisible();
  await expect(page.getByTestId("usage-workspaces")).toBeVisible();
  await expect(page.getByTestId("usage-storage")).toBeVisible();
});
