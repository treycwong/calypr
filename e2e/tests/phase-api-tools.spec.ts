import { expect, type Page, test } from "@playwright/test";

// API-as-a-tool gate (Phase 8a): external APIs reach the canvas as *providers on the existing
// Tool node*, so the LLM decides when to call them (ReAct), rather than a node fetching
// deterministically. Two surfaces are covered: the Unsplash preset (key from Settings, stub
// results without one) and `generic_http` (any public GET API).
//
// Everything here runs keyless — no Unsplash key, no database, no network — because the
// Unsplash tool falls back to deterministic stub photos, exactly like `demo_search`. The
// live-key path is covered by the node unit test.

async function openCanvas(page: Page) {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.locator(".react-flow__controls")).toBeVisible();
}

async function loadTemplate(page: Page, name: string) {
  await page.getByTestId("tab-templates").click();
  await page.getByTestId("templates-panel").getByRole("button", { name, exact: true }).click();
  await page.getByTestId("template-apply").click();
}

test("the Image Finder template projects to an Unsplash tool over the ReAct loop", async ({
  page,
}) => {
  await openCanvas(page);

  await loadTemplate(page, "Image Finder");
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await expect(page.getByTestId("node-tool")).toBeVisible();

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  await expect(code).toContainText("def build_graph():", { timeout: 15_000 });
  await expect(code).toContainText("def search_images(");
  await expect(code).toContainText("api.unsplash.com");
  await expect(code).toContainText("tools_condition");
  await expect(code).toContainText(".bind_tools(");
  // The key is runtime-only: generated code reads the environment, never an inlined secret.
  await expect(code).toContainText("os.environ['UNSPLASH_ACCESS_KEY']");
});

test("switching the Tool provider to Unsplash swaps in the key hint", async ({ page }) => {
  await openCanvas(page);

  await page.getByTestId("add-tool").click();
  await expect(page.getByTestId("node-tool")).toBeVisible();
  await page.getByTestId("node-tool").click();

  // demo_search shows a raw API-key box; Unsplash takes its key from Settings instead, so the
  // box goes away and the panel says where the key lives.
  await expect(page.getByTestId("cfg-api-key")).toBeVisible();
  await page.getByTestId("cfg-provider").selectOption("images_unsplash");

  await expect(page.getByTestId("cfg-api-key")).toHaveCount(0);
  await expect(page.getByText("Settings → API Keys")).toBeVisible();
});

test("the HTTP provider exposes URL, params, and response path", async ({ page }) => {
  await openCanvas(page);

  await page.getByTestId("add-tool").click();
  await page.getByTestId("node-tool").click();
  await page.getByTestId("cfg-provider").selectOption("generic_http");

  await expect(page.getByTestId("cfg-http-url")).toBeVisible();
  await expect(page.getByTestId("cfg-http-params")).toBeVisible();
  await expect(page.getByTestId("cfg-jsonpath")).toBeVisible();
  await expect(page.getByTestId("cfg-api-key")).toHaveCount(0);

  await page.getByTestId("cfg-http-url").fill("https://api.example.com/search");
  await page.getByTestId("cfg-http-params").fill("q={query}");
  await expect(page.getByTestId("cfg-http-url")).toHaveValue("https://api.example.com/search");

  await page.getByTestId("toggle-code").click();
  const code = page.getByTestId("code-output");
  // The emitted module is ruff-formatted, so string literals come back double-quoted.
  await expect(code).toContainText('_HTTP_URL = "https://api.example.com/search"', {
    timeout: 15_000,
  });
  await expect(code).toContainText("def fetch(");
});

test("the Unsplash graph compiles and runs on the canvas with no key", async ({ page }) => {
  await openCanvas(page);
  await loadTemplate(page, "Image Finder");

  // Deterministic + keyless: the fake model never asks for a tool, so this asserts what the
  // canvas guarantee actually is — a graph containing an Unsplash tool compiles and runs with
  // no key on file. Whether the tool call itself round-trips is the node unit test's job
  // (`packages/nodes/tests/test_http_tools.py`), which drives a tool-calling fake model.
  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");

  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("chat-input").fill("find me a photo of a foggy forest");
  await page.getByTestId("chat-send").click();

  await expect(page.getByTestId("msg-assistant").last()).toContainText(
    "Echo: find me a photo of a foggy forest",
    { timeout: 15_000 },
  );
});

test("a photo the agent returns renders as an inline preview, not a bare link", async ({
  page,
}) => {
  // The found photo is only previewed when the agent emits markdown *image* syntax — the
  // leading `!`. Without it the Markdown renderer leaves a plain link and the user sees a URL,
  // which is exactly what shipped in the first cut of this template. The fake model echoes the
  // message back, so this exercises Markdown → ChatImage with a real Unsplash URL (query string
  // and all) without needing a key.
  const url =
    "https://images.unsplash.com/photo-1496588152823-86ff7695e68f?crop=entropy&fm=jpg&w=64";
  await openCanvas(page);
  await loadTemplate(page, "Image Finder");
  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");

  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("chat-input").fill(`![Manhattan in the distance](${url})`);
  await page.getByTestId("chat-send").click();

  const img = page.getByTestId("msg-assistant").last().locator("img");
  await expect(img).toBeVisible({ timeout: 15_000 });
  await expect(img).toHaveAttribute("src", url);
  await expect(img).toHaveAttribute("alt", "Manhattan in the distance");
});
