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

test("Workflows and Usage are reachable from the sidebar", async ({ page }) => {
  await signIn(page);

  // The workflow library: real starters, grouped by the job they do. Frameworks are excluded by
  // design — they live on the canvas rail, next to the wiring they describe.
  await page.getByTestId("nav-workflows").click();
  await expect(page.getByRole("heading", { name: "Workflows" })).toBeVisible();
  await expect(page.getByTestId("workflow-grid")).toBeVisible();
  // One flat grid — no category headings. The order still comes from CATEGORY_ORDER, so study
  // leads; the grouping survives as sequence, which is what a filter will key off later.
  await expect(page.getByTestId("workflow-card").first()).toHaveAttribute(
    "data-category",
    "Study & revision",
  );

  // Covers are committed URLs, not a runtime search — asserted on the attribute, never on the
  // pixels, so this gate does not depend on images.unsplash.com being reachable from CI.
  const first = page.getByTestId("workflow-card").first();
  await expect(first.locator("img")).toHaveAttribute("src", /images\.unsplash\.com/);
  // The Unsplash licence asks for a photographer credit linking back, with referral params.
  await expect(first.getByTestId("workflow-credit")).toHaveAttribute(
    "href",
    /unsplash\.com\/@.+utm_source=calypr/,
  );
  // The credit is a real link, so it must not be nested inside the card's button.
  await expect(first.getByTestId("workflow-credit").locator("xpath=ancestor::button")).toHaveCount(
    0,
  );
  await expect(
    page.getByTestId("workflow-card").filter({ hasText: "Language flash cards" }),
  ).toBeVisible();
  // A framework must not appear in a gallery of jobs to do.
  await expect(page.getByTestId("workflow-card").filter({ hasText: "ReAct" })).toHaveCount(0);

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
// therefore invisible to `page.route` — see the header above), the card reads `/api/workspace`
// client-side, so the plan's limits and the account's usage *are* mockable here.

/** Mock the singular workspace payload the card gates and confirms on. */
async function mockWorkspace(
  page: import("@playwright/test").Page,
  { name = "Side project", allowed = 3, owned = 2 } = {},
) {
  await page.route("**/api/workspace", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      json: {
        id: "w2",
        name,
        plan: allowed > 1 ? "plus" : "free",
        limits: { projects: 20, workspaces: allowed, monthly_credits: 0, storage_bytes: 0 },
        usage: { projects: 2, workspaces: owned, storage_bytes: 0 },
      },
    });
  });
}

async function openWorkspaceTab(page: import("@playwright/test").Page) {
  // Click through to the tab rather than deep-linking `?tab=workspace`: the dev sign-in redirect
  // drops the query string, so the deep link silently lands on the Account tab.
  await signInAt(page, "/dashboard/settings");
  await page.getByTestId("tab-workspace").click();
  // Something from the tab, so the assertions below distinguish "card absent" from "tab not open".
  await expect(page.getByTestId("ws-name")).toBeVisible();
}

test("a single-workspace plan holding one workspace is not offered the card at all", async ({
  page,
}) => {
  // The Free case. A permanently disabled destructive control is clutter, so it isn't rendered.
  await mockWorkspace(page, { name: "Personal", allowed: 1, owned: 1 });
  await openWorkspaceTab(page);
  await expect(page.getByTestId("ws-danger-card")).toHaveCount(0);
});

test("a lapsed plan still holding several workspaces keeps the card", async ({ page }) => {
  // The case a literal "plus only" gate would break: a downgraded account keeps its workspaces
  // with the excess read-only (`locking.py`), and deleting one is how it gets back under the cap.
  // Gating on the plan *name* would strand exactly the people who most need this.
  await mockWorkspace(page, { name: "Side project", allowed: 1, owned: 2 });
  await openWorkspaceTab(page);
  await expect(page.getByTestId("ws-danger-card")).toBeVisible();
  await expect(page.getByTestId("ws-delete-open")).toBeEnabled();
});

test("a multi-workspace plan down to its last workspace is told why it can't delete", async ({
  page,
}) => {
  await mockWorkspace(page, { name: "Personal", allowed: 3, owned: 1 });
  await openWorkspaceTab(page);
  // Mirrored from the server rather than enforced here: reaching a dead end after typing out a
  // workspace name is a worse way to learn the rule than never being offered the button.
  await expect(page.getByTestId("ws-delete-only-notice")).toBeVisible();
  await expect(page.getByTestId("ws-delete-open")).toBeDisabled();
});

test("deleting a workspace needs its name typed exactly, and names what it will destroy", async ({
  page,
}) => {
  let deletedId: string | null = null;

  await mockWorkspace(page, { name: "Side project", allowed: 3, owned: 2 });
  await page.route("**/api/agents", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    return route.fulfill({
      json: [
        { id: "a1", name: "One", updated_at: new Date().toISOString(), locked: false },
        { id: "a2", name: "Two", updated_at: new Date().toISOString(), locked: false },
      ],
    });
  });
  await page.route("**/api/workspaces/*", async (route) => {
    if (route.request().method() !== "DELETE") return route.fallback();
    deletedId = route.request().url().split("/").pop() ?? null;
    return route.fulfill({ status: 204, body: "" });
  });

  await openWorkspaceTab(page);

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
