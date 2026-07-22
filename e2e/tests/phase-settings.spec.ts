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

test("the Connectors tab opens the panel with all sections", async ({ page }) => {
  await openCanvas(page);

  await page.getByTestId("tab-connectors").click();
  const panel = page.getByTestId("connectors-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByText("Connected accounts")).toBeVisible();
  // Tier A: the catalog lives behind "Add Connection"; Notion is the one entry today.
  await expect(page.getByTestId("connect-notion")).toHaveCount(0);
  await page.getByTestId("connection-add-open").click();
  await expect(page.getByTestId("connect-notion")).toBeVisible();
  await page.keyboard.press("Escape");
  // Tier B ("paste your own MCP server URL") is no longer offered: it's a bring-your-own-server
  // path and the servers people run are on their own machine, which this cloud backend can't
  // reach. The section renders only for a workspace that already saved one, and never with an
  // add form. App connections above are the supported path.
  //
  // Asserts the *add* affordances are gone, not that the section is absent: a workspace that
  // saved a server before this change still lists it (so it stays removable), and this suite
  // shares a workspace with whatever the developer has saved. Asserting absence here would pass
  // on a clean machine and fail on a real one.
  await expect(page.getByTestId("mcp-add-open")).toHaveCount(0);
  await expect(page.getByTestId("mcp-url")).toHaveCount(0);
  await expect(page.getByTestId("mcp-name")).toHaveCount(0);
  // API Keys: a provider dropdown; the key input appears only after a provider is picked.
  await expect(page.getByTestId("key-provider")).toBeVisible();
  await expect(page.getByTestId("key-input")).toHaveCount(0);
  await page.getByTestId("key-provider").selectOption("openai");
  await expect(page.getByTestId("key-input")).toBeVisible();
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
