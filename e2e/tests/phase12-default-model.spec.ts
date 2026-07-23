import { expect, test } from "@playwright/test";

// The workspace default model (Settings → Workspace). Blocks ship `model: ""` — inherit — so
// this one setting decides what the whole canvas runs on, and an untouched workspace has to
// land on a real model rather than the `fake` test seam that answers "Echo: …".

test("the Workspace tab exposes the default model picker", async ({ page }) => {
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  const picker = page.getByTestId("ws-default-model");
  await expect(picker).toBeVisible();
  // "" is the inherit sentinel, and the label has to name what it actually resolves to —
  // "Workspace default → ?" would tell the user nothing.
  await expect(picker.locator("option[value='']")).toContainText("gpt-4o-mini");
  await expect(picker.locator("option[value='gpt-4o']")).toHaveCount(1);
});

test("the default model saves and survives a reload", async ({ page }) => {
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  const picker = page.getByTestId("ws-default-model");
  await picker.selectOption("gpt-4o");
  await expect(page.getByText("Saved ✓")).toBeVisible();

  await page.reload();
  await page.getByTestId("tab-workspace").click();
  await expect(page.getByTestId("ws-default-model")).toHaveValue("gpt-4o");

  // Put it back so the shared dev workspace doesn't leak this choice into other specs.
  await page.getByTestId("ws-default-model").selectOption("");
  await expect(page.getByText("Saved ✓")).toBeVisible();
});

test("a new Agent block inherits instead of naming a model", async ({ page }) => {
  // The canvas half of the same rule: dragging a block on and never opening its config must
  // still produce a working agent. Router/Evaluator/Memory/Responder/Revisor used to default
  // to `fake` here, which shipped canned "Echo:" answers to anyone who used them.
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page.locator(".react-flow__controls")).toBeVisible();

  await page.getByTestId("add-agent").click();
  await page.getByTestId("node-agent").click();
  await expect(page.getByTestId("cfg-model")).toHaveValue("");
});

// The plan indicator on Settings → Account. "Can I export my code?" should have a visible
// answer where people look, rather than being inferred from whether the Code tab works.
test("the Account tab shows the workspace plan", async ({ page }) => {
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();

  const badge = page.getByTestId("account-plan");
  await expect(badge).toBeVisible();
  // The E2E workspace is `free`, so the badge says so and offers the way out.
  await expect(badge).toHaveText("Free");
  await expect(page.getByText("Code export is a Plus feature.")).toBeVisible();
  await expect(page.getByTestId("account-upgrade")).toHaveAttribute("href", "/pricing");
});

test("an entitled plan says what it includes and offers no upgrade", async ({ page }) => {
  // The control: the copy has to be driven by the plan, not hard-coded next to the badge.
  await page.route("**/api/workspace", (route) =>
    route.fulfill({ json: workspacePayload({ plan: "plus" }) }),
  );
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();

  await expect(page.getByTestId("account-plan")).toHaveText("Plus");
  await expect(page.getByText(/yours to edit, download and run anywhere/)).toBeVisible();
  await expect(page.getByTestId("account-upgrade")).toHaveCount(0);
});

/** A complete workspace payload, so the stub never round-trips upstream.
 *
 * `route.fetch()` + modify races the test teardown: the assertion resolves, the test ends, and
 * the in-flight upstream fetch errors — which surfaced as whichever credit test happened to run
 * last failing. Fulfilling synthetically removes the race and makes each test state explicit. */
function workspacePayload(over: Record<string, unknown> = {}) {
  return {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Dev Workspace",
    plan: "free",
    signed_in_as: null,
    assistant_model: "",
    default_model: "",
    credits: { allowance: 0, remaining: 0, used: 0 },
    ...over,
  };
}

// Usage display. Enforcement without a display is a limit nobody can plan around: a run
// refused for "no credits" is only actionable if you can see where you stood.
test("Settings shows the credit balance", async ({ page }) => {
  await page.route("**/api/workspace", (route) =>
    route.fulfill({ json: workspacePayload({ credits: { allowance: 2000, remaining: 1487, used: 513 } }) }),
  );
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  const panel = page.getByTestId("ws-credits");
  await expect(panel).toBeVisible();
  await expect(page.getByTestId("ws-credits-remaining")).toHaveText("1,487");
  await expect(panel).toContainText("of 2,000 credits left");
  // BYO-key runs cost nothing — the sentence that stops the panel reading as a hard wall.
  await expect(panel).toContainText("your own API key");
});

test("an exhausted balance says what to do about it", async ({ page }) => {
  await page.route("**/api/workspace", (route) =>
    route.fulfill({ json: workspacePayload({ plan: "free", credits: { allowance: 100, remaining: 0, used: 100 } }) }),
  );
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();

  await expect(page.getByTestId("ws-credits")).toContainText("out of credits");
  await expect(page.getByTestId("ws-credits")).toContainText("upgrade to Plus");
});

test("the panel is hidden when there is no allowance", async ({ page }) => {
  // A workspace with no grant (the shared dev/anonymous one) shouldn't show an empty meter.
  await page.route("**/api/workspace", (route) =>
    route.fulfill({ json: workspacePayload({ credits: { allowance: 0, remaining: 0, used: 0 } }) }),
  );
  await page.goto("/dashboard/settings");
  await page.getByTestId("dev-sign-in").click();
  await page.getByTestId("tab-workspace").click();
  // Wait for the tab to actually render before asserting an absence — otherwise the assertion
  // passes instantly against a page that hasn't loaded, and the test ends mid-route-fetch.
  await expect(page.getByTestId("ws-default-model")).toBeVisible();
  await expect(page.getByTestId("ws-credits")).toHaveCount(0);
});
