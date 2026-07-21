import { expect, type Page, test } from "@playwright/test";

import { API_URL } from "../playwright.config";

// Phase 8 gate (MVP-EXECUTION-PLAN Week 8): the reverse round-trip reaches the user. Open a
// graph, drop into the Code tab, hand-edit the Python, and "Apply to canvas" turns it back into
// nodes — then the edited agent still runs. Keyless (the "fake" model), no database needed.
//
// The round-trip UI is gated off by default (it is deliberately not live in production), so each
// test opts in via localStorage before the app boots. That keeps the Code tab a read-only `<pre>`
// for every other spec — only here is it a `<textarea>`.

const PROMPT = "Original prompt here.";
const EDITED = "Edited by hand in the code tab.";

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("calypr:roundtrip", "1"));
});

async function openCanvas(page: Page) {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.locator(".react-flow__controls")).toBeVisible();
}

/** Input → Agent → Output on the keyless model, with a known prompt to look for in the code. */
async function buildAgent(page: Page, prompt = PROMPT) {
  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-agent").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await page.getByTestId("add-output").click();
  await expect(page.getByTestId("node-output")).toBeVisible();

  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");
  await expect(page.getByTestId("cfg-model")).toHaveValue("fake");
  await page.getByTestId("cfg-prompt").fill(prompt);
}

async function openCodeTab(page: Page) {
  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toHaveValue(/def build_graph\(\):/, { timeout: 15_000 });
  return code;
}

test("a hand-edited prompt applies back to the canvas", async ({ page }) => {
  await openCanvas(page);
  await buildAgent(page);
  const code = await openCodeTab(page);

  // Apply stays inert until the code actually differs from what we generated.
  await expect(page.getByTestId("apply-to-canvas")).toBeDisabled();

  const original = await code.inputValue();
  expect(original).toContain(PROMPT);
  await code.fill(original.replace(PROMPT, EDITED));

  await expect(page.getByTestId("apply-to-canvas")).toBeEnabled();
  await page.getByTestId("apply-to-canvas").click();
  await expect(page.getByTestId("parse-notice")).toContainText("Applied to canvas");

  // The canvas was rebuilt from the parsed code — every node survives the trip...
  await expect(page.getByTestId("node-input")).toBeVisible();
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await expect(page.getByTestId("node-output")).toBeVisible();

  // ...and the edit landed in the graph, not just the text buffer.
  await page.getByTestId("node-agent").click();
  await expect(page.getByTestId("cfg-prompt")).toHaveValue(EDITED);
});

test("an edited agent still runs after being applied", async ({ page }) => {
  await openCanvas(page);
  await buildAgent(page);
  const code = await openCodeTab(page);

  const original = await code.inputValue();
  await code.fill(original.replace(PROMPT, EDITED));
  await page.getByTestId("apply-to-canvas").click();
  await expect(page.getByTestId("parse-notice")).toContainText("Applied to canvas");

  // The round-tripped graph is a real graph: it compiles and streams a reply.
  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("chat-input").fill("hello roundtrip");
  await page.getByTestId("chat-send").click();
  await expect(page.getByTestId("msg-assistant").last()).toContainText(
    "Echo: hello roundtrip",
    { timeout: 30_000 },
  );
});

test("unparseable code is reported, and the canvas is left alone", async ({ page }) => {
  await openCanvas(page);
  await buildAgent(page);
  const code = await openCodeTab(page);

  await code.fill("def build_graph(:\n"); // deliberately broken
  await page.getByTestId("apply-to-canvas").click();

  // Fail-safe: the user is told, and the existing canvas survives.
  await expect(page.getByTestId("parse-notice")).toBeVisible();
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await expect(page.getByTestId("node-input")).toBeVisible();
});

test("a hand-written step comes back as a custom-code node, not a failure", async ({
  page,
}) => {
  await openCanvas(page);
  await buildAgent(page);
  const code = await openCodeTab(page);

  // Insert a node no recogniser can match — the graceful-degradation contract, end to end.
  const original = await code.inputValue();
  const withCustom = original
    .replace(
      "def build_graph():",
      [
        "def node_tally(state: State) -> dict:",
        '    """Something I wrote myself."""',
        '    return {"tally": 1}',
        "",
        "",
        "def build_graph():",
      ].join("\n"),
    )
    .replace(
      "    return graph.compile()",
      '    graph.add_node("tally", node_tally)\n    return graph.compile()',
    );
  await code.fill(withCustom);
  await page.getByTestId("apply-to-canvas").click();

  // Applied, with an honest note about what wasn't understood.
  await expect(page.getByTestId("parse-notice")).toContainText("custom code");
  await expect(page.getByTestId("node-code")).toBeVisible();
});

test("the round-trip UI is hidden unless it is switched on", async ({ browser }) => {
  // A fresh context with no opt-in — i.e. exactly what production serves today.
  const context = await browser.newContext();
  const page = await context.newPage();
  await openCanvas(page);
  await buildAgent(page);

  await page.getByTestId("toggle-code").click();
  await expect(page.getByTestId("code-output")).toContainText("def build_graph():", {
    timeout: 15_000,
  });
  // Read-only `<pre>`, and no way to apply anything back.
  await expect(page.getByTestId("apply-to-canvas")).toHaveCount(0);
  await context.close();
});

test("a beta workspace gets the round-trip with no local opt-in", async ({
  browser,
  request,
}) => {
  // The real cohort gate, end to end: promote the workspace through the operator endpoint and
  // the Code tab becomes editable for a browser that has set nothing at all. This is what a
  // beta design partner will actually experience.
  const ws = await (await request.get(`${API_URL}/workspaces/current`)).json();
  const promote = (plan: string) =>
    request.post(`${API_URL}/admin/workspaces/${ws.id}/plan`, {
      data: { plan },
      headers: { "x-admin-token": "e2e-admin-token" },
    });

  expect((await promote("beta")).ok()).toBeTruthy();
  const context = await browser.newContext(); // no localStorage opt-in
  try {
    const page = await context.newPage();
    await openCanvas(page);
    await buildAgent(page);
    await page.getByTestId("toggle-code").click();
    await expect(page.getByTestId("apply-to-canvas")).toBeVisible({ timeout: 15_000 });
  } finally {
    // Restore `free` — the test above asserts the UI is hidden, and both run against the same
    // database.
    await promote(ws.plan ?? "free");
    await context.close();
  }
});
