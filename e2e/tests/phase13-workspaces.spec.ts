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

// --- Delete workspace ---------------------------------------------------------------------
//
// The card is on Settings → Workspace. Unlike the layout's workspace list (server-fetched, and
// therefore invisible to `page.route` — see the header above), this card does its own client-side
// reads, so how many workspaces exist and how many projects are at stake *are* mockable here.

async function openWorkspaceSettings(page: import("@playwright/test").Page) {
  // Click through to the tab rather than deep-linking `?tab=workspace`: the dev sign-in redirect
  // drops the query string, so the deep link silently lands on the Account tab.
  await signInAt(page, "/dashboard/settings");
  await page.getByTestId("tab-workspace").click();
  await expect(page.getByTestId("ws-danger-card")).toBeVisible();
}

test("the only workspace can't be deleted, and the card says why", async ({ page }) => {
  await page.route("**/api/workspaces", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      json: { workspaces: [{ id: "w1", name: "Personal", is_current: true }], can_create: true },
    });
  });

  await openWorkspaceSettings(page);
  // Refusing in the UI *and* on the server is deliberate: reaching a dead end after typing out a
  // workspace name is a worse way to learn the rule than never being offered the button.
  await expect(page.getByTestId("ws-delete-only-notice")).toBeVisible();
  await expect(page.getByTestId("ws-delete-open")).toBeDisabled();
});

test("deleting a workspace needs its name typed exactly, and names what it will destroy", async ({
  page,
}) => {
  let deletedId: string | null = null;

  await page.route("**/api/workspaces", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      json: {
        workspaces: [
          { id: "w1", name: "Personal", is_current: false },
          { id: "w2", name: "Side project", is_current: true },
        ],
        can_create: true,
      },
    });
  });
  await page.route("**/api/agents", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      json: [
        { id: "a1", name: "One", updated_at: new Date().toISOString(), locked: false },
        { id: "a2", name: "Two", updated_at: new Date().toISOString(), locked: false },
      ],
    });
  });
  // The name typed to confirm is matched against the *saved* workspace, which comes from the
  // singular `/api/workspace` — not from the list above. Mocking only the list would leave the
  // card comparing against whatever the real dev workspace is called.
  await page.route("**/api/workspace", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({ json: { id: "w2", name: "Side project", plan: "free" } });
  });
  await page.route("**/api/workspaces/*", async (route) => {
    if (route.request().method() !== "DELETE") return route.fallback();
    deletedId = route.request().url().split("/").pop() ?? null;
    return route.fulfill({ status: 204, body: "" });
  });

  await openWorkspaceSettings(page);

  // The count is fetched rather than described in the abstract — "2 projects" is something you
  // can weigh, where "your projects" is a phrase people click past.
  await expect(page.getByTestId("ws-delete-projects")).toContainText("2 projects");

  await page.getByTestId("ws-delete-open").click();
  const confirm = page.getByTestId("ws-delete-confirm");
  await expect(confirm).toBeDisabled();

  // The name of a *different* workspace must not arm it — that is the whole point of typing the
  // name rather than a fixed phrase.
  await page.getByTestId("ws-delete-input").fill("Personal");
  await expect(confirm).toBeDisabled();

  // Case and surrounding space are forgiven; the name itself is not.
  await page.getByTestId("ws-delete-input").fill("  side PROJECT ");
  await expect(confirm).toBeEnabled();

  await confirm.click();
  await expect.poll(() => deletedId).toBe("w2");
});
