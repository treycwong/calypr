import { expect, type Page, test } from "@playwright/test";

import { signInAt } from "./helpers";

// MCP node gate: an MCP server's tools reach the canvas through the existing Tool seam. The
// MCP ReAct framework projects to a `MultiServerMCPClient` over the canonical `ToolNode` +
// `tools_condition` loop, reading its URL/token from the environment (secrets never emitted);
// and the Tool node's provider dropdown exposes MCP-specific fields. Viewing code needs no
// key, no database, and no live MCP server — the live run is covered by the node unit test.

async function openCanvas(page: Page) {
  await signInAt(page, "/canvas");
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.locator(".react-flow__controls")).toBeVisible();
}

async function loadFramework(page: Page, name: string) {
  await page.getByTestId("tab-templates").click();
  await page.getByTestId("templates-panel").getByRole("button", { name, exact: true }).click();
  await page.getByTestId("template-apply").click();
}

test("the MCP ReAct framework projects to MultiServerMCPClient over the tool loop", async ({
  page,
}) => {
  await openCanvas(page);

  await loadFramework(page, "MCP ReAct");
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await expect(page.getByTestId("node-tool")).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  await expect(code).toContainText("MultiServerMCPClient");
  await expect(code).toContainText("tools_condition");
  await expect(code).toContainText(".bind_tools(");
  // Secrets are runtime-only: the URL is read from the environment, never inlined.
  await expect(code).toContainText('os.environ["MCP_URL"]');
});

test("the GitHub + Notion template projects to two independent MCP servers", async ({
  page,
}) => {
  await openCanvas(page);

  await loadFramework(page, "GitHub + Notion");
  // Multi-server MCP is two Tool nodes, one connection each — not one node with two servers.
  await expect(page.getByTestId("node-tool")).toHaveCount(2);

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  // Two clients reading two env vars: a single pair would mean both nodes silently share one
  // server, which is the failure this template exists to prevent.
  await expect(code).toContainText('os.environ["MCP_URL"]');
  await expect(code).toContainText('os.environ["MCP_URL_2"]');
  await expect(code).toContainText("ToolNode([*mcp_tools])");
  await expect(code).toContainText("ToolNode([*mcp_tools_2])");
  // And the agent routes to whichever node owns a call, rather than one `tools` branch.
  await expect(code).toContainText("tools_github");
  await expect(code).toContainText("tools_notion");
});

test("switching the Tool provider to MCP reveals the server fields", async ({
  page,
}) => {
  await openCanvas(page);

  await page.getByTestId("add-tool").click();
  await expect(page.getByTestId("node-tool")).toBeVisible();
  await page.getByTestId("node-tool").click();

  // demo_search shows the API-key/max-results fields; MCP swaps them for the server fields.
  await expect(page.getByTestId("cfg-api-key")).toBeVisible();
  await page.getByTestId("cfg-provider").selectOption("mcp");

  await expect(page.getByTestId("cfg-mcp-url")).toBeVisible();
  await expect(page.getByTestId("cfg-mcp-transport")).toBeVisible();
  await expect(page.getByTestId("cfg-mcp-token")).toBeVisible();
  await expect(page.getByTestId("cfg-api-key")).toHaveCount(0);
});
