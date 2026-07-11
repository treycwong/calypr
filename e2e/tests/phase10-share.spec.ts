import { expect, type Page, test } from "@playwright/test";

// Phase 10 gate (WEEK3-SHARE-LINKS-PLAN §C): an owner builds + saves an agent, mints a share
// link, and a LOGGED-OUT visitor opens /s/{token}, sees the agent name (never the spec), and
// gets a streamed reply. Revoking the link makes it unavailable. Uses the keyless "fake" model,
// so the gate needs no provider key (CI provides Postgres + `alembic upgrade head`).

async function buildAndSaveAgent(page: Page): Promise<string> {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.locator(".react-flow__controls")).toBeVisible();

  await page.getByTestId("add-input").click();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await page.getByTestId("add-agent").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await page.getByTestId("add-output").click();
  await expect(page.getByTestId("node-output")).toBeVisible();

  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");
  await expect(page.getByTestId("cfg-model")).toHaveValue("fake");

  await page.getByTestId("agent-name").fill("Shared Bot");
  await page.getByTestId("save-agent").click();
  await expect(page.getByTestId("save-msg")).toContainText("Saved");

  // The Share button only appears once the agent has an id (i.e. after Save).
  await expect(page.getByTestId("share-agent")).toBeVisible();
  // Opening the popover mints the link; capture the token from the proxied response.
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/share") && r.request().method() === "POST"),
    page.getByTestId("share-agent").click(),
  ]);
  const { token } = (await res.json()) as { token: string };
  expect(token).toBeTruthy();
  // The popover shows the link URL + a Copy button.
  await expect(page.getByTestId("share-panel")).toBeVisible();
  await expect(page.getByTestId("share-url")).toHaveValue(new RegExp(`/s/${token}$`));
  await page.getByTestId("share-copy").click();
  await expect(page.getByTestId("share-copy")).toContainText("Copied");
  return token;
}

test("a logged-out visitor can open a share link and get a streamed reply", async ({
  page,
  browser,
}) => {
  const token = await buildAndSaveAgent(page);

  // Open the link in a fresh, logged-OUT context (no dev session cookie).
  const anon = await browser.newContext();
  const anonPage = await anon.newPage();
  await anonPage.goto(`/s/${token}`);

  // The agent name shows; the page must never carry the graph spec.
  await expect(anonPage.getByTestId("share-agent-name")).toContainText("Shared Bot");
  const html = await anonPage.content();
  expect(html).not.toContain("graph_spec");
  expect(html).not.toContain("system_prompt");

  // Run it — the fake model echoes the message back, streamed.
  await anonPage.getByTestId("chat-input").fill("hi there");
  await anonPage.getByTestId("chat-send").click();
  await expect(anonPage.getByTestId("msg-assistant").last()).toContainText("Echo: hi there", {
    timeout: 15_000,
  });

  await anon.close();
});

test("revoking a link makes it unavailable", async ({ page, browser }) => {
  const token = await buildAndSaveAgent(page);

  // Revoke through the authenticated API (the owner's session drives the proxy). The agent id
  // isn't needed in the URL beyond routing, so derive it from the current canvas URL.
  const agentId = new URL(page.url()).searchParams.get("agent");
  expect(agentId).toBeTruthy();
  const del = await page.request.delete(`/api/agents/${agentId}/share/${token}`);
  expect(del.ok()).toBeTruthy();

  // A logged-out visitor now sees the unavailable state, and a run is refused.
  const anon = await browser.newContext();
  const anonPage = await anon.newPage();
  await anonPage.goto(`/s/${token}`);
  await expect(anonPage.getByTestId("share-unavailable")).toBeVisible();
  await anon.close();
});
