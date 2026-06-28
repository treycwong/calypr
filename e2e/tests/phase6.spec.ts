import { expect, type Page, test } from "@playwright/test";

// Phase 6 gate: the user dashboard. Dev sign-in lands on the dashboard shell; New Project
// creates a real agent (which opens on the canvas) that then shows in the Projects grid and
// can be renamed + deleted; Settings shows the account/workspace tabs. Needs the database
// (agent CRUD), so it runs in CI where Postgres is available.

async function signIn(page: Page) {
  await page.goto("/dashboard");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/dashboard/);
}

test("the dashboard shell renders the sidebar nav", async ({ page }) => {
  await signIn(page);
  await expect(page.getByTestId("nav-projects")).toBeVisible();
  await expect(page.getByTestId("nav-settings")).toBeVisible();
  await expect(page.getByTestId("sign-out")).toBeVisible();
});

test("create a project, see it on the dashboard, rename it, then delete it", async ({
  page,
}) => {
  await signIn(page);
  const unique = `E2E ${Date.now()}`;

  // New Project → name it → Blank → lands on the canvas for the freshly-created agent.
  await page.getByTestId("new-project").click();
  await expect(page).toHaveURL(/\/dashboard\/new/);
  await page.getByTestId("new-name").fill(unique);
  await page.getByTestId("start-blank").click();
  await expect(page).toHaveURL(/\/canvas\?agent=[0-9a-f-]+/, { timeout: 15_000 });

  // Back on the dashboard, the project is listed.
  await page.goto("/dashboard");
  const card = page.getByTestId("project-card").filter({ hasText: unique });
  await expect(card).toBeVisible({ timeout: 15_000 });

  // Rename it.
  await card.getByTestId("project-menu").click();
  await page.getByTestId("project-rename").click();
  const renamed = `${unique} renamed`;
  await page.getByTestId("rename-input").fill(renamed);
  await page.getByTestId("rename-save").click();
  const renamedCard = page.getByTestId("project-card").filter({ hasText: renamed });
  await expect(renamedCard).toBeVisible({ timeout: 15_000 });

  // Delete it.
  await renamedCard.getByTestId("project-menu").click();
  await page.getByTestId("project-delete").click();
  await page.getByTestId("delete-confirm").click();
  await expect(
    page.getByTestId("project-card").filter({ hasText: renamed }),
  ).toHaveCount(0, { timeout: 15_000 });
});

test("the settings page shows the account + workspace tabs", async ({ page }) => {
  await signIn(page);
  await page.getByTestId("nav-settings").click();
  await expect(page).toHaveURL(/\/dashboard\/settings/);
  await expect(page.getByTestId("tab-account")).toBeVisible();
  await expect(page.getByTestId("tab-workspace")).toBeVisible();
});
