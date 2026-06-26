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
  // a Knowledge node grounds the research agent, then the specialists each become a function
  await expect(code).toContainText("def node_research");
  await expect(code).toContainText("def node_editor");
});

// Phase 5c gate: RAG reaches the canvas. The RAG framework projects to a self-contained,
// keyless vector-store retriever (InMemoryVectorStore + DeterministicFakeEmbedding), and the
// Knowledge node's source dropdown reveals a pgvector collection field.

test("the RAG framework loads a Knowledge node and projects to a vector-store retriever", async ({
  page,
}) => {
  await openCanvas(page);

  await page.getByTestId("template-picker").selectOption({ label: "RAG (retrieval)" });
  await expect(page.getByTestId("node-retriever")).toBeVisible();
  await expect(page.getByTestId("node-agent")).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  await expect(code).toContainText("InMemoryVectorStore");
  await expect(code).toContainText("DeterministicFakeEmbedding");
});

test("the Knowledge node exposes a source dropdown; pgvector reveals a collection field", async ({
  page,
}) => {
  await openCanvas(page);

  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-retriever").click();
  await expect(page.getByTestId("node-retriever")).toBeVisible();

  await page.getByTestId("node-retriever").click();
  await expect(page.getByTestId("cfg-source")).toBeVisible();
  await expect(page.getByTestId("cfg-top-k")).toBeVisible();
  // demo source hides the collection; switching to pgvector reveals it
  await expect(page.getByTestId("cfg-collection")).toHaveCount(0);
  await page.getByTestId("cfg-source").selectOption("pgvector");
  await expect(page.getByTestId("cfg-collection")).toBeVisible();
});

// Phase 5d gate: LLM-based routing. The Routing framework projects to an init_chat_model
// classifier wired through add_conditional_edges; the Router's "Decide by" toggle switches
// between Python rules and an LLM classifier (which reveals a model picker).

test("the Routing framework loads an LLM router and projects to a classifier", async ({
  page,
}) => {
  await openCanvas(page);

  await page.getByTestId("template-picker").selectOption({ label: "Routing" });
  await expect(page.getByTestId("node-router")).toBeVisible();
  await expect(page.getByTestId("node-agent").first()).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  await expect(code).toContainText("init_chat_model");
  await expect(code).toContainText("add_conditional_edges");
});

test("the Router 'Decide by' toggle reveals a model picker in LLM mode", async ({
  page,
}) => {
  await openCanvas(page);

  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-router").click();
  await expect(page.getByTestId("node-router")).toBeVisible();

  await page.getByTestId("node-router").click();
  await expect(page.getByTestId("cfg-router-kind")).toBeVisible();
  // rules mode: no model picker; switching to LLM reveals it
  await expect(page.getByTestId("cfg-model")).toHaveCount(0);
  await page.getByTestId("cfg-router-kind").selectOption("llm");
  await expect(page.getByTestId("cfg-model")).toBeVisible();
});
