import { expect, type Page, test } from "@playwright/test";

// Settings + connectors gate: the Settings sidebar tab opens the panel where MCP/OAuth
// connectors are managed (Connected Accounts + MCP Servers), and an MCP Tool node exposes a
// "Connector" dropdown that references those saved connectors. This asserts the DB-independent
// UI surface (the connector CRUD itself is covered by the API tests); it runs whether or not a
// database is wired, so it stays deterministic in CI.

async function openCanvas(page: Page) {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.locator(".react-flow__controls")).toBeVisible();
}

test("the Settings tab opens the connectors panel", async ({ page }) => {
  await openCanvas(page);

  await page.getByTestId("tab-settings").click();
  const panel = page.getByTestId("settings-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByText("Connected accounts")).toBeVisible();
  await expect(page.getByTestId("connect-notion")).toBeVisible();
  // The Tier B add-server form is present.
  await expect(page.getByTestId("mcp-url")).toBeVisible();
  await expect(page.getByTestId("mcp-add")).toBeVisible();
});

test("an MCP Tool node exposes a Connector dropdown", async ({ page }) => {
  await openCanvas(page);

  await page.getByTestId("add-tool").click();
  await expect(page.getByTestId("node-tool")).toBeVisible();
  await page.getByTestId("node-tool").click();

  await page.getByTestId("cfg-provider").selectOption("mcp");
  // The connector dropdown (Settings-backed) is the primary path; manual URL is the fallback.
  await expect(page.getByTestId("cfg-mcp-connector")).toBeVisible();
  // With no connector selected, the manual URL field is shown.
  await expect(page.getByTestId("cfg-mcp-url")).toBeVisible();
});
