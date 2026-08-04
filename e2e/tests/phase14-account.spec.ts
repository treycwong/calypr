import { expect, type Page, test } from "@playwright/test";

// Settings → Account: profile, integrations, and Delete Account.
//
// These run in **dev mode**, like the whole suite. That shapes what is worth asserting: there is
// no profile store behind the dev session, so the name/avatar fields are deliberately disabled
// and the interesting surface is the delete flow — which the API 501s and the web proxy
// translates into a success, so the confirm → cookies cleared → redirect path is fully
// exercisable without ever deleting anything.
//
// The negative test (Cancel leaves you signed in) matters more than the positive one. A confirm
// dialog that destroys an account when you decline is the failure nobody recovers from.

async function openAccountTab(page: Page) {
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await expect(page.getByTestId("account-info-card")).toBeVisible();
}

/** Open the delete dialog, retrying until it is actually up.
 *
 * Same hydration race as `phase13-workspaces.spec.ts`: the button is server-rendered and
 * clickable before React attaches, so a click landing in that window does nothing and the next
 * locator waits out its full timeout. */
async function openDeleteDialog(page: Page) {
  await expect(async () => {
    await page.getByTestId("account-delete-open").click();
    await expect(page.getByTestId("account-delete-input")).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 15_000 });
}

test("the Account tab shows the three cards", async ({ page }) => {
  await openAccountTab(page);

  await expect(page.getByTestId("account-info-card")).toBeVisible();
  await expect(page.getByTestId("account-integrations-card")).toBeVisible();
  await expect(page.getByTestId("account-danger-card")).toBeVisible();

  // The plan badge and upgrade link survive the rebuild — `phase12-default-model.spec.ts`
  // depends on them and they are the answer to "why can't I export my code?".
  await expect(page.getByTestId("account-plan")).toBeVisible();
});

test("dev mode disables the profile fields and says why", async ({ page }) => {
  await openAccountTab(page);

  await expect(page.getByTestId("account-name")).toBeDisabled();
  await expect(page.getByTestId("account-image")).toBeDisabled();
  await expect(page.getByTestId("account-save")).toBeDisabled();
  await expect(page.getByTestId("account-dev-notice")).toBeVisible();
});

test("email is shown as text, with no input to edit it", async ({ page }) => {
  await openAccountTab(page);

  // Read-only means *no field*, not a disabled one: the API trusts this address as the
  // provider-verified one, so an editable email would be a way to self-grant beta.
  await expect(page.getByTestId("account-email")).toBeVisible();
  await expect(page.getByTestId("account-info-card").locator("#account-email-input")).toHaveCount(
    0,
  );
});

test("the GitHub integration reports its connected state", async ({ page }) => {
  await openAccountTab(page);

  // Dev sign-in links no provider, so this is the honest answer here.
  await expect(page.getByTestId("account-integration-github")).toHaveAttribute(
    "data-connected",
    "false",
  );
});

test("the confirm button stays disabled until the exact phrase is typed", async ({ page }) => {
  await openAccountTab(page);
  await openDeleteDialog(page);

  const confirm = page.getByTestId("account-delete-confirm");
  await expect(confirm).toBeDisabled();

  await page.getByTestId("account-delete-input").fill("delete");
  await expect(confirm).toBeDisabled();

  await page.getByTestId("account-delete-input").fill("delete my account!");
  await expect(confirm).toBeDisabled();

  // Case and surrounding whitespace are forgiven — the friction is the point, not pedantry.
  await page.getByTestId("account-delete-input").fill("  Delete My Account  ");
  await expect(confirm).toBeEnabled();
});

test("Cancel closes the dialog and leaves you signed in", async ({ page }) => {
  // **The important negative test.** Everything else here can be wrong and merely annoy; this
  // being wrong destroys an account for someone who said no.
  await openAccountTab(page);
  await openDeleteDialog(page);

  await page.getByTestId("account-delete-input").fill("delete my account");
  await expect(page.getByTestId("account-delete-confirm")).toBeEnabled();

  await page.getByRole("button", { name: "Cancel" }).click();

  await expect(page.getByTestId("account-delete-input")).toBeHidden();
  await expect(page).toHaveURL(/\/dashboard\/settings/);
  await expect(page.getByTestId("account-danger-card")).toBeVisible();

  // Still authenticated: the dashboard doesn't bounce us to sign-in.
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/dashboard/);
  await expect(page.getByTestId("dev-sign-in")).toHaveCount(0);
});

test("confirming signs you out and the dashboard no longer lets you in", async ({ page }) => {
  await openAccountTab(page);
  await openDeleteDialog(page);

  await page.getByTestId("account-delete-input").fill("delete my account");
  await page.getByTestId("account-delete-confirm").click();

  // The API 501s in dev and the proxy reports success, so the flow completes for real: cookies
  // cleared, redirected to sign-in with the acknowledgement.
  await expect(page).toHaveURL(/\/sign-in\?deleted=1/, { timeout: 15_000 });
  await expect(page.getByTestId("account-deleted-notice")).toBeVisible();

  // And the session is genuinely gone — /dashboard bounces back to sign-in.
  await page.goto("/dashboard");
  await expect(page.getByTestId("dev-sign-in")).toBeVisible();
});
