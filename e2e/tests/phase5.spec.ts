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

// Templates moved from a header dropdown to the left icon-rail's Templates panel.
async function loadTemplate(page: Page, name: string) {
  await page.getByTestId("tab-templates").click();
  // Exact match: "ReAct" must not also select "MCP ReAct" (substring) — strict-mode safe.
  await page
    .getByTestId("templates-panel")
    .getByRole("button", { name, exact: true })
    .click();
  // A preview modal opens first; Apply swaps the canvas nodes.
  await page.getByTestId("template-apply").click();
}

test("the ReAct template projects to the canonical ToolNode + tools_condition loop", async ({
  page,
}) => {
  await openCanvas(page);

  await loadTemplate(page, "ReAct");
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

// Reversed 2026-07-22 (Phase 2c). Phase 5a dropped this dropdown — "the templates carry the
// type now" — and this test pinned its absence. The config-panel audit made the cost visible:
// a hand-built Agent could never leave `model_based`, and the goal/reflection/utility fields in
// the same panel were unreachable dead UI. The selector is back, and the assertion is inverted
// rather than deleted, so the history of the decision stays legible.
test("the Agent panel offers the agent-type ladder", async ({ page }) => {
  await openCanvas(page);

  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-agent").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();

  await page.getByTestId("node-agent").click();
  await expect(page.getByTestId("cfg-model")).toBeVisible(); // the panel is showing
  const type = page.getByTestId("cfg-agent-type");
  await expect(type).toBeVisible();
  // Templates still carry a type — this is the default for a block you drew yourself.
  await expect(type).toHaveValue("model_based");
});

test("the Reflexion template projects its Responder/Revisor bounded loop into code", async ({
  page,
}) => {
  await openCanvas(page);

  await loadTemplate(page, "Reflexion");
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

  await loadTemplate(page, "Market research report");
  await expect(page.getByTestId("node-agent").first()).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  // a Knowledge node grounds the research agent, then the specialists each become a function
  await expect(code).toContainText("def node_research");
  await expect(code).toContainText("def node_editor");
});

// Phase 5c gate: RAG reaches the canvas. The RAG framework projects to a PGVector retriever
// (the default Knowledge source) against the user's own Postgres, and the Knowledge node's
// source dropdown can switch to the keyless demo store.

test("the RAG framework loads a Knowledge node and projects to a vector-store retriever", async ({
  page,
}) => {
  await openCanvas(page);

  await loadTemplate(page, "RAG (retrieval)");
  await expect(page.getByTestId("node-retriever")).toBeVisible();
  await expect(page.getByTestId("node-agent")).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  // the default Knowledge source is pgvector → owned PGVector + OpenAI embeddings
  await expect(code).toContainText("PGVector");
  await expect(code).toContainText("OpenAIEmbeddings");
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
  // default pgvector shows the collection field; switching to demo hides it
  await expect(page.getByTestId("cfg-collection")).toBeVisible();
  await page.getByTestId("cfg-source").selectOption("demo");
  await expect(page.getByTestId("cfg-collection")).toHaveCount(0);
});

// Phase 5d gate: LLM-based routing. The Summarize-or-translate template projects to an
// init_chat_model classifier wired through add_conditional_edges; the Router's "Decide by"
// toggle switches between Python rules and an LLM classifier (which reveals a model picker).

test("the Summarize-or-translate template loads an LLM router and projects to a classifier", async ({
  page,
}) => {
  await openCanvas(page);

  await loadTemplate(page, "Summarize or translate");
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

// Phase 5e gate: the Orchestrator–Worker template. An orchestrator fans out to parallel
// specialist agents that fan in to a synthesizer; it projects to idiomatic LangGraph where
// the workers each become a function and the synthesizer merges them.

test("the Trip-itinerary template fans out to parallel workers and a synthesizer", async ({
  page,
}) => {
  await openCanvas(page);

  await loadTemplate(page, "Trip itinerary planner");
  await expect(page.getByTestId("node-agent").first()).toBeVisible();

  // Role agents are named, not all "Agent", and the flow runs left → right.
  const orchestrator = page.getByText("Orchestrator", { exact: true });
  const synthesizer = page.getByText("Synthesizer", { exact: true });
  await expect(orchestrator).toBeVisible();
  await expect(synthesizer).toBeVisible();
  const ob = await orchestrator.boundingBox();
  const sb = await synthesizer.boundingBox();
  expect(ob && sb && ob.x < sb.x).toBeTruthy(); // orchestrator sits left of the synthesizer

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  // each specialist + the synthesizer becomes its own function
  await expect(code).toContainText("def node_flights");
  await expect(code).toContainText("def node_synthesizer");
});

test("a template previews in a modal; Apply swaps nodes without renaming the project", async ({
  page,
}) => {
  await openCanvas(page);

  // Name the project, then open a template — a preview modal appears (not an instant load).
  await page.getByTestId("agent-name").fill("My Project");
  await page.getByTestId("tab-templates").click();
  await page.getByTestId("templates-panel").getByRole("button", { name: "ReAct", exact: true }).click();
  await expect(page.getByTestId("template-modal")).toBeVisible();

  // Cancel leaves the canvas untouched.
  await page.getByTestId("template-cancel").click();
  await expect(page.getByTestId("template-modal")).toHaveCount(0);
  await expect(page.getByTestId("node-agent")).toHaveCount(0);

  // Apply swaps in the template's nodes but keeps the project name.
  await page.getByTestId("templates-panel").getByRole("button", { name: "ReAct", exact: true }).click();
  await page.getByTestId("template-apply").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await expect(page.getByTestId("agent-name")).toHaveValue("My Project");
});

test("undo and redo step the canvas through add-node history", async ({ page }) => {
  await openCanvas(page);

  // Undo/redo start disabled (no history yet).
  await expect(page.getByTestId("undo")).toBeDisabled();
  await expect(page.getByTestId("redo")).toBeDisabled();

  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-agent").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();

  // Undo removes the agent, then the input.
  await page.getByTestId("undo").click();
  await expect(page.getByTestId("node-agent")).toHaveCount(0);
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("undo").click();
  await expect(page.getByTestId("node-input")).toHaveCount(0);
  await expect(page.getByTestId("undo")).toBeDisabled();

  // Redo brings them back in order.
  await page.getByTestId("redo").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("redo").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await expect(page.getByTestId("redo")).toBeDisabled();
});

test("the right panel toggles Properties/Code; the rail AI panel is single-select", async ({
  page,
}) => {
  await openCanvas(page);

  // The right panel switches between the Code view and node Properties.
  await page.getByTestId("toggle-code").click();
  await expect(page.getByTestId("code-panel")).toBeVisible();
  await page.getByTestId("tab-properties").click();
  await expect(page.getByTestId("code-panel")).toHaveCount(0);

  // The rail is single-select: opening AI replaces the Blocks palette (add-input disappears).
  await expect(page.getByTestId("add-input")).toBeVisible();
  await page.getByTestId("toggle-assistant").click();
  await expect(page.getByTestId("assistant-panel")).toBeVisible();
  await expect(page.getByTestId("add-input")).toHaveCount(0);
  // The assistant is functional: its input is enabled (Send stays disabled until you type).
  await expect(page.getByTestId("assistant-input")).toBeEnabled();
});
