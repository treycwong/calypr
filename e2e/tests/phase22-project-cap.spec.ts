import { expect, test } from "@playwright/test";

import { signInAt } from "./helpers";

// A free account is capped at 3 projects, and creating one is the only thing on the dashboard a
// plan refuses. It used to surface as `save failed (402)` — a status code, shown to someone in
// the middle of starting work. It now opens a pricing card that says what they hit.
//
// Both paths are stubbed, the way the workspace-cap spec stubs its 402, because caps are not
// enforced without an internal key: dev and CI deliberately let every create through, so a real
// cap cannot be reached here. What is under test is the client's handling of the API's answer.

/** The 402 `create_agent` sends when the account is out of slots. */
const CAP_402 = {
  status: 402,
  json: {
    detail: {
      reason: "project_cap",
      limit: 3,
      used: 3,
      plan: "free",
      message: "You've used 3 of 3 projects on Free.",
    },
  },
};

test("a workflow card refused by the project cap offers the upgrade", async ({ page }) => {
  await page.route("**/api/agents", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    return route.fulfill(CAP_402);
  });

  await signInAt(page, "/dashboard/workflows");
  await page.getByTestId("workflow-card").first().click();

  const dialog = page.getByTestId("upgrade-dialog");
  await expect(dialog).toBeVisible();
  // The server's own sentence, not one reconstructed here: it knows the real count and plan.
  await expect(dialog).toContainText("3 of 3 projects on Free");
  // The comparison is the point: Free as it stands, next to what Plus changes.
  await expect(dialog).toContainText("$20/mo");
  // Five rows since the 3D block joined the comparison — the count is pinned so a row added
  // without a thought about this dialog fails here rather than quietly stretching it.
  await expect(dialog.getByTestId("plan-row")).toHaveCount(5);
  await expect(dialog.getByTestId("plan-row").first()).toContainText("Projects");
  await expect(dialog).toContainText("Code export");
  await expect(page.getByTestId("upgrade-cta")).toHaveAttribute("href", "/checkout?plan=plus");
  // We stayed put — a refused create must not strand someone on a half-made canvas.
  await expect(page).toHaveURL(/\/dashboard\/workflows/);

  // Dismissable: a paywall that traps you is worse than the error it replaced.
  await page.getByTestId("upgrade-dismiss").click();
  await expect(dialog).toBeHidden();
});

test("New Project answers in place when the API says there is no room", async ({ page }) => {
  // `can_create_project` rides along with the workspace list, so the button can answer without a
  // request — and without the browser deciding for itself what the plan allows.
  await page.route("**/api/workspaces", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    const res = await route.fetch();
    const body = await res.json();
    return route.fulfill({ json: { ...body, can_create_project: false } });
  });

  await signInAt(page, "/dashboard");
  // The button reads state the page fetches after mount, so wait for the stub to have landed
  // rather than racing it.
  await page.waitForResponse((r) => r.url().includes("/api/workspaces"));
  await page.getByTestId("new-project").click();

  await expect(page.getByTestId("upgrade-dialog")).toBeVisible();
  await expect(page).toHaveURL(/\/dashboard$/); // it did not navigate to the create form
});

test("New Project navigates normally when there is room", async ({ page }) => {
  await signInAt(page, "/dashboard");
  await page.getByTestId("new-project").click();
  await expect(page).toHaveURL(/\/dashboard\/new/);
  await expect(page.getByTestId("upgrade-dialog")).toBeHidden();
});
