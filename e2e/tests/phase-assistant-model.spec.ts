import { expect, type Page, test } from "@playwright/test";

// Dashboard → Settings → Workspace exposes the AI assistant's default model. The options come
// from the API's allow-list, and frontier models (kimi-k3) are disabled until the workspace has
// that provider's own key on file — the picker must never offer a value /assist would refuse.

test("the Workspace tab exposes the assistant model picker", async ({ page }) => {
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/dashboard\/settings/);

  await page.getByTestId("tab-workspace").click();

  const picker = page.getByTestId("ws-assistant-model");
  await expect(picker).toBeVisible();
  // Populated from GET /assistant-models, not a hard-coded client list.
  await expect(picker.locator("option")).not.toHaveCount(0);
  await expect(picker.locator("option[value='gpt-4o-mini']")).toHaveCount(1);
});

const MOONSHOT_ON_FILE = "moonshot";

/** Pin which providers have a BYO key on file. Stubbed rather than written to the database:
 *  the E2E API shares the developer's dev workspace, so a real key saved in Settings would
 *  otherwise decide whether this test passes. */
async function withProviderKeys(page: Page, onFile: string[]) {
  await page.route("**/api/provider-keys", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      json: ["openai", "anthropic", "moonshot", "tavily"].map((provider) => ({
        provider,
        has_key: onFile.includes(provider),
      })),
    });
  });
}

test("kimi-k3 is offered but disabled without a Moonshot key", async ({ page }) => {
  await withProviderKeys(page, []);
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  const frontier = page
    .getByTestId("ws-assistant-model")
    .locator("option[value='kimi-k3']");
  await expect(frontier).toHaveCount(1);
  // Visible, so users can see the model exists — but not selectable, and the label says why.
  await expect(frontier).toBeDisabled();
  await expect(frontier).toContainText("add your own key");
});

test("kimi-k3 becomes selectable once a Moonshot key is on file", async ({ page }) => {
  await withProviderKeys(page, ["moonshot"]);
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  const frontier = page
    .getByTestId("ws-assistant-model")
    .locator("option[value='kimi-k3']");
  await expect(frontier).toBeEnabled();
  await expect(frontier).not.toContainText("add your own key");
});

test("the provider list offers a live Kimi key and Coming Soon rows", async ({ page }) => {
  await withProviderKeys(page, []);
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  // Moonshot is wired, so its input is live and Save waits for input.
  const kimi = page.getByTestId("ws-key-moonshot");
  await expect(kimi).toBeEnabled();
  await expect(kimi).toHaveAttribute("type", "password");
  await expect(page.getByTestId("ws-key-moonshot-save")).toBeDisabled();
  await kimi.fill("sk-typed-in-the-browser");
  await expect(page.getByTestId("ws-key-moonshot-save")).toBeEnabled();

  // OpenAI and Anthropic are wired too, so their inputs are live as well.
  for (const provider of ["openai", "anthropic"]) {
    await expect(page.getByTestId(`ws-key-${provider}`)).toBeEnabled();
    await expect(page.getByTestId(`ws-key-${provider}-soon`)).toHaveCount(0);
  }

  // Google has no client in the model factory — visible but inert, and unstorable.
  for (const provider of ["google"]) {
    await expect(page.getByTestId(`ws-key-${provider}-soon`)).toHaveText("Coming soon");
    await expect(page.getByTestId(`ws-key-${provider}`)).toBeDisabled();
    await expect(page.getByTestId(`ws-key-${provider}-save`)).toBeDisabled();
  }
});

test("the headline model for each provider is named", async ({ page }) => {
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  for (const model of [
    "kimi-k3",
    "GPT-4o · GPT-4o mini",
    "Claude Opus 4.8",
    "Gemini Pro",
  ]) {
    await expect(page.getByText(model, { exact: true })).toBeVisible();
  }
});

test("a stored key shows as on-file and is never echoed back", async ({ page }) => {
  await withProviderKeys(page, [MOONSHOT_ON_FILE]);
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  await expect(page.getByTestId("ws-key-moonshot-onfile")).toBeVisible();
  await expect(page.getByTestId("ws-key-moonshot-remove")).toBeVisible();
  // The input stays empty — the API never returns a stored key, and the UI must not pretend to.
  await expect(page.getByTestId("ws-key-moonshot")).toHaveValue("");
});

test("a Coming Soon provider never shows key controls, even with a key on file", async ({
  page,
}) => {
  // Even if a key were somehow on file for an unwired provider, the row must not imply it is
  // usable — nothing in the model factory would read it.
  await withProviderKeys(page, ["google"]);
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  await expect(page.getByTestId("ws-key-google-onfile")).toHaveCount(0);
  await expect(page.getByTestId("ws-key-google-remove")).toHaveCount(0);
  await expect(page.getByTestId("ws-key-google")).toBeDisabled();
});

test("Moonshot is no longer offered in the canvas API-keys panel", async ({ page }) => {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-connectors").click();

  // Moved to Dashboard → Settings → Workspace, so there is exactly one place to manage it.
  const options = page.getByTestId("key-provider").locator("option");
  await expect(options.filter({ hasText: "Moonshot" })).toHaveCount(0);
  // The other providers still live here.
  await expect(options.filter({ hasText: "OpenAI" })).toHaveCount(1);
});

test("choosing a non-frontier model persists across a reload", async ({ page }) => {
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  const picker = page.getByTestId("ws-assistant-model");
  await picker.selectOption("gpt-4o-mini");
  await expect(page.getByText("Saved ✓")).toBeVisible();

  await page.reload();
  await page.getByTestId("tab-workspace").click();
  await expect(page.getByTestId("ws-assistant-model")).toHaveValue("gpt-4o-mini");

  // Leave the workspace on the server default so other specs are unaffected.
  await page.getByTestId("ws-assistant-model").selectOption("");
  await expect(page.getByText("Saved ✓")).toBeVisible();
});

test("a run on an unkeyed frontier model falls back and says so", async ({ page }) => {
  // The picker disables these, so reach the state the picker can't cover: a graph that already
  // names a frontier model (imported, API-built, or keyed and then un-keyed).
  await page.route("**/api/runs", async (route) => {
    const body = JSON.parse(route.request().postData() ?? "{}");
    for (const n of body.graph?.nodes ?? []) {
      if (n.type === "agent") n.config = { ...n.config, model: "kimi-k3" };
    }
    await route.continue({ postData: JSON.stringify(body) });
  });

  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page.locator(".react-flow__controls")).toBeVisible();

  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-agent").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await page.getByTestId("add-output").click();
  await expect(page.getByTestId("node-output")).toBeVisible();

  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("chat-input").fill("hello");
  await page.getByTestId("chat-send").click();

  // The transcript names both the model that ran and the one that was asked for.
  const reply = page.getByTestId("msg-assistant").last();
  await expect(reply).toContainText("gpt-4o-mini", { timeout: 30_000 });
  await expect(reply).toContainText("kimi-k3");
  await expect(reply).toContainText("Settings");
});
