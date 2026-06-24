import { expect, type Page, test } from "@playwright/test";

// Phase 5a gate: tools reach the canvas. The ReAct template projects to the canonical
// LangGraph tool loop (`ToolNode` + `tools_condition`); the Tool node exposes a provider
// dropdown + API-key input; and the Agent panel no longer has an agent-type dropdown (the
// templates carry the type now). Viewing code needs no API key and no database.

async function openCanvas(page: Page) {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.locator(".react-flow__controls")).toBeVisible();
}

test("the ReAct template projects to the canonical ToolNode + tools_condition loop", async ({
  page,
}) => {
  await openCanvas(page);

  await page.getByTestId("template-picker").selectOption({ label: "ReAct" });
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await expect(page.getByTestId("node-tool")).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  await expect(code).toContainText("ToolNode");
  await expect(code).toContainText("tools_condition");
  await expect(code).toContainText(".bind_tools(");
});

test("the Tool node exposes a provider dropdown and an API-key input", async ({
  page,
}) => {
  await openCanvas(page);

  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-tool").click();
  await expect(page.getByTestId("node-tool")).toBeVisible();

  await page.getByTestId("node-tool").click();
  await expect(page.getByTestId("cfg-provider")).toBeVisible();
  await expect(page.getByTestId("cfg-api-key")).toBeVisible();
});

test("the Agent panel no longer has an agent-type dropdown", async ({ page }) => {
  await openCanvas(page);

  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-agent").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();

  await page.getByTestId("node-agent").click();
  await expect(page.getByTestId("cfg-model")).toBeVisible(); // the panel is showing
  await expect(page.getByTestId("cfg-agent-type")).toHaveCount(0); // but no type selector
});

test("the Reflexion template projects its Responder/Revisor bounded loop into code", async ({
  page,
}) => {
  await openCanvas(page);

  await page.getByTestId("template-picker").selectOption({ label: "Reflexion" });
  await expect(page.getByTestId("node-responder")).toBeVisible();
  await expect(page.getByTestId("node-revisor")).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  await expect(code).toContainText("def node_responder");
  await expect(code).toContainText("def route_node_revisor"); // the bounded loop
  await expect(code).toContainText("revision_count");
});

test("a use-case template loads a multi-agent pipeline and projects to code", async ({
  page,
}) => {
  await openCanvas(page);

  await page
    .getByTestId("template-picker")
    .selectOption({ label: "Market research report" });
  await expect(page.getByTestId("node-agent").first()).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  // the specialist agents become one function each
  await expect(code).toContainText("def node_research");
  await expect(code).toContainText("def node_editor");
});
