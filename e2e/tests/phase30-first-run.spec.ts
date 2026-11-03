import { expect, test } from "@playwright/test";

import { signInAt } from "./helpers";

// The first run (walkthrough of 2026-11-03). A new account used to meet an empty dashboard with
// no template on it, a gallery that opened on ten textbook "frameworks", a project named
// "Untitled Agent", and a chat that said only "Send a message to test your agent". This walks the
// path a newcomer takes and pins each fix.
//
// The run itself is not exercised: templates use a real model and CI has no key. What a newcomer
// needs from this path is to arrive at a ready chat that says what to type.

test("an empty dashboard offers templates that open straight into a ready chat", async ({
  page,
}) => {
  // The shared dev workspace already has projects, so the empty state is staged. Only the list
  // is faked; creating the project is real.
  await page.route("**/api/agents", (route) =>
    route.request().method() === "GET" ? route.fulfill({ json: [] }) : route.fallback(),
  );
  await signInAt(page, "/dashboard");

  const starters = page.getByTestId("starter-templates");
  await expect(starters).toBeVisible();
  // Study first: it is the first category, and the plan we sell is "practising every day".
  const first = starters.getByRole("button").first();
  await expect(first).toContainText("Language flash cards");

  await first.click();
  await expect(page).toHaveURL(/\/canvas\?agent=[0-9a-f-]+&starter=tpl-flashcards/, {
    timeout: 15_000,
  });
  const agentId = new URL(page.url()).searchParams.get("agent");

  // The project carries the template's name, not "Untitled Agent".
  await expect(page.getByTestId("agent-name")).toHaveValue("Language flash cards");

  // The chat is already open, offering something to try. A starter fills the composer rather
  // than sending, so it can still be edited (or an image attached) first.
  await expect(page.getByTestId("playground")).toBeVisible();
  const chips = page.getByTestId("chat-starters").getByRole("button");
  await expect(chips.first()).toHaveText("Spanish greetings");
  await chips.first().click();
  await expect(page.getByTestId("chat-input")).toHaveValue("Spanish greetings");

  // Tidy up: the dev workspace is shared across specs and the free plan caps projects.
  await page.unroute("**/api/agents");
  expect((await page.request.delete(`/api/agents/${agentId}`)).ok()).toBe(true);
});

test("the new-project page leads with templates and names the project after the one picked", async ({
  page,
}) => {
  await signInAt(page, "/dashboard/new");
  const templates = page.getByTestId("gallery-templates");
  const frameworks = page.getByTestId("gallery-frameworks");
  await expect(templates).toBeVisible();
  await expect(frameworks).toBeVisible();

  // Templates above frameworks.
  const [tBox, fBox] = await Promise.all([templates.boundingBox(), frameworks.boundingBox()]);
  expect(tBox!.y).toBeLessThan(fBox!.y);

  // The name box is empty, so the template's own name wins.
  await expect(page.getByTestId("new-name")).toHaveValue("");
  await templates.getByRole("button", { name: /Quiz me on anything/ }).click();
  await expect(page).toHaveURL(/starter=tpl-quiz-me/, { timeout: 15_000 });
  await expect(page.getByTestId("agent-name")).toHaveValue("Quiz me on anything");
  const agentId = new URL(page.url()).searchParams.get("agent");
  expect((await page.request.delete(`/api/agents/${agentId}`)).ok()).toBe(true);
});
