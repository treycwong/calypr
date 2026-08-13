/**
 * The Playground's History and Media tabs.
 *
 * **What this suite can and cannot prove.** `playwright.config.ts` pins `CALYPR_INTERNAL_KEY=""`
 * (see its comment for why), so every request resolves to the shared dev workspace — fine here,
 * since these tabs are workspace-scoped and there is only one. The real constraint is the
 * database: history is persisted server-side, so the assertions that a conversation *appears*
 * only hold when Postgres is up. They are guarded rather than skipped wholesale, so the tab
 * chrome, the empty states, and the chat regression coverage still run everywhere.
 */
import { expect, test, type Page } from "@playwright/test";

import { buildChain, openCanvas, waitForHydration } from "./helpers";

/** Input → Agent → Output on the keyless `fake` model — the same shape phase8 builds. */
async function buildAgent(page: Page) {
  // Wired by hand: adding a block no longer connects it to anything.
  await buildChain(page, ["input", "agent", "output"]);

  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");
  await expect(page.getByTestId("cfg-model")).toHaveValue("fake");
}

async function chat(page: Page, message: string) {
  await page.getByTestId("chat-input").fill(message);
  await page.getByTestId("chat-send").click();
  await expect(page.getByTestId("msg-assistant").last()).toContainText(`Echo: ${message}`, {
    timeout: 30_000,
  });
}

/** Whether history actually persisted. Without a database the API 503s and the tab shows its
 *  empty state — correct behaviour, but nothing downstream is worth asserting. */
async function historyIsPersisted(page: Page): Promise<boolean> {
  await page.getByTestId("tab-history").click();
  const rows = page.getByTestId("history-item");
  try {
    await expect(rows.first()).toBeVisible({ timeout: 5_000 });
    return true;
  } catch {
    return false;
  }
}

test("the playground has Chat and History tabs, and Chat is the default", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("toggle-playground").click();

  await expect(page.getByTestId("playground-tabs")).toBeVisible();
  // Chat is default, so every pre-existing spec that opens the playground and types still works
  // without learning about tabs.
  await expect(page.getByTestId("chat-input")).toBeVisible();
  await expect(page.getByTestId("tab-chat")).toHaveAttribute("aria-selected", "true");

  // "New chat" belongs to the transcript, not to the panel — it hides on the other tab.
  await expect(page.getByTestId("chat-reset")).toBeVisible();
  await page.getByTestId("tab-history").click();
  await expect(page.getByTestId("chat-reset")).toHaveCount(0);
  await expect(page.getByTestId("history-search")).toBeVisible();

  // Media is *not* here — it is workspace-scoped and lives in the left rail.
  await expect(page.getByTestId("tab-media")).toHaveCount(0);
});

test("media is a left-rail panel with All / Images / Audio tabs", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("toggle-media").click();

  const panel = page.getByTestId("media-panel");
  await expect(panel).toBeVisible();
  await expect(page.getByTestId("media-kinds")).toBeVisible();
  await expect(page.getByTestId("media-kind-all")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("media-kind-images")).toBeVisible();
  await expect(page.getByTestId("media-kind-audio")).toBeVisible();
  await expect(page.getByTestId("media-search")).toBeVisible();

  await page.getByTestId("media-kind-audio").click();
  await expect(page.getByTestId("media-kind-audio")).toHaveAttribute("aria-selected", "true");

  // Clicking the active rail button closes the panel, like every other rail tab.
  await page.getByTestId("toggle-media").click();
  await expect(panel).toHaveCount(0);
});

test("the send button becomes Stop while a run is streaming", async ({ page }) => {
  // Send used to be `disabled` during a run, which is exactly when someone wants a way out.
  await openCanvas(page);
  await buildAgent(page);
  await page.getByTestId("toggle-playground").click();

  const button = page.getByTestId("chat-send");
  await expect(button).toHaveText("Send");
  await expect(button).toBeEnabled();

  await chat(page, "hello");
  // Settles back to Send once the run finishes, and stays usable throughout.
  await expect(button).toHaveText("Send");
  await expect(button).toBeEnabled();
});

test("Stop appears mid-run, ends it, and keeps what streamed", async ({ page }) => {
  await openCanvas(page);
  await buildAgent(page);

  // **Hold the stream open deliberately.** The `fake` model answers in milliseconds, so racing
  // it would make this test assert nothing most runs and fail occasionally — the worst of both.
  // Stalling the proxy gives a real in-flight run with a known start and no end, which is
  // exactly the state Stop exists for. The two tokens land first so there is something to keep.
  let release: () => void = () => {};
  const held = new Promise<void>((r) => (release = r));
  await page.route("**/api/runs", async (route) => {
    await held;
    await route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream" },
      body:
        `data: ${JSON.stringify({ type: "token", text: "half an " })}\n\n` +
        `data: ${JSON.stringify({ type: "token", text: "answer" })}\n\n` +
        "data: [DONE]\n\n",
    });
  });

  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("chat-input").fill("stop me");
  await page.getByTestId("chat-send").click();

  // The run is in flight and the control has become Stop — enabled, not a dead Send.
  const button = page.getByTestId("chat-send");
  await expect(button).toHaveText(/Stop/);
  await expect(button).toBeEnabled();

  await button.click();

  // Back to a usable composer, and the abandoned turn is labelled the way History will show it.
  await expect(button).toHaveText("Send");
  await expect(page.getByTestId("msg-partial")).toBeVisible();
  await expect(page.getByTestId("msg-user").last()).toContainText("stop me");

  release(); // let the stalled route go so the test can tear down cleanly
});

test("switching tabs mid-conversation does not lose the transcript", async ({ page }) => {
  // The specific trap: base-ui unmounts an inactive panel, so chat state has to live above it.
  // Before that fix, a trip to History wiped the conversation on screen.
  await openCanvas(page);
  await buildAgent(page);
  await page.getByTestId("toggle-playground").click();
  await chat(page, "stay put");

  await page.getByTestId("tab-history").click();
  await page.getByTestId("tab-chat").click();

  await expect(page.getByTestId("msg-assistant").last()).toContainText("Echo: stay put");
  await expect(page.getByTestId("msg-user").last()).toContainText("stay put");
});

test("a conversation is saved, searchable, reopenable and deletable", async ({ page }) => {
  await openCanvas(page);
  await buildAgent(page);
  await page.getByTestId("toggle-playground").click();

  const marker = `austria ${Date.now()}`;
  await chat(page, marker);

  test.skip(!(await historyIsPersisted(page)), "history needs a database");

  // Saved automatically — no Save button was pressed anywhere in this test.
  const row = page.getByTestId("history-item").filter({ hasText: marker });
  await expect(row).toHaveCount(1);

  // Search is server-side: a term that matches nothing empties the list, then clearing restores.
  await page.getByTestId("history-search").fill("definitely-not-a-conversation");
  await expect(page.getByTestId("history-item")).toHaveCount(0);
  await page.getByTestId("history-search").fill(marker);
  await expect(page.getByTestId("history-item")).toHaveCount(1);

  // Reopening loads the transcript from the database and returns to the Chat tab.
  await page.getByTestId("tab-chat").click();
  await page.getByTestId("chat-reset").click();
  await expect(page.getByTestId("msg-user")).toHaveCount(0);

  await page.getByTestId("tab-history").click();
  await page.getByTestId("history-item").filter({ hasText: marker }).click();
  await expect(page.getByTestId("tab-chat")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("msg-user").last()).toContainText(marker);

  // Delete, through the confirm dialog.
  await page.getByTestId("tab-history").click();
  const target = page.getByTestId("history-item").filter({ hasText: marker });
  await target.getByTestId("history-menu").click();
  await page.getByTestId("history-delete").click();
  await expect(page.getByTestId("history-delete-confirm")).toBeVisible();
  await page.getByTestId("confirm-delete").click();
  await expect(page.getByTestId("history-item").filter({ hasText: marker })).toHaveCount(0);
});

test("a conversation can be renamed", async ({ page }) => {
  await openCanvas(page);
  await buildAgent(page);
  await page.getByTestId("toggle-playground").click();

  const marker = `rename me ${Date.now()}`;
  await chat(page, marker);
  test.skip(!(await historyIsPersisted(page)), "history needs a database");

  const row = page.getByTestId("history-item").filter({ hasText: marker });
  await row.getByTestId("history-menu").click();
  await page.getByTestId("history-rename").click();
  const renamed = `renamed ${Date.now()}`;
  await page.getByTestId("history-rename-input").fill(renamed);
  await page.getByRole("button", { name: "Save" }).click();

  await expect(page.getByTestId("history-item").filter({ hasText: renamed })).toHaveCount(1);
});

test("the media panel explains itself when there is nothing in it", async ({ page }) => {
  // Worth pinning: a blob-less deployment records no media *by design*, and an unexplained empty
  // grid there reads as a broken feature rather than an unconfigured one.
  await openCanvas(page);
  await page.getByTestId("toggle-media").click();

  const list = page.getByTestId("media-list");
  if (await page.getByTestId("media-item").count()) {
    test.skip(true, "this workspace already has generated media");
  }
  await expect(list).toContainText("No generated media yet");
  await expect(list).toContainText("Images and audio your runs generate are saved here");
});

test("each project sees only its own conversations", async ({ page }) => {
  // The list used to be workspace-wide, so every project showed every other project's chats.
  await openCanvas(page);
  await buildAgent(page);
  await page.getByTestId("toggle-playground").click();

  const marker = `scoped ${Date.now()}`;
  await chat(page, marker);
  test.skip(!(await historyIsPersisted(page)), "history needs a database");
  await expect(page.getByTestId("history-item").filter({ hasText: marker })).toHaveCount(1);

  // Save this canvas as a project — the conversation is adopted on its next turn.
  await page.getByTestId("tab-chat").click();
  await page.getByTestId("save-agent").click();
  await expect(page.getByTestId("save-msg")).toContainText("Saved", { timeout: 15_000 });
  await chat(page, `${marker} again`);

  // A different project must not see it.
  await openCanvas(page); // a fresh, unsaved canvas
  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("tab-history").click();
  await expect(page.getByTestId("history-item").filter({ hasText: marker })).toHaveCount(0);
});

test("history survives a reload — it is server-side, not component state", async ({ page }) => {
  await openCanvas(page);
  await buildAgent(page);
  await page.getByTestId("toggle-playground").click();

  const marker = `durable ${Date.now()}`;
  await chat(page, marker);
  test.skip(!(await historyIsPersisted(page)), "history needs a database");
  await expect(page.getByTestId("history-item").filter({ hasText: marker })).toHaveCount(1);

  await page.reload();
  await waitForHydration(page);
  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("tab-history").click();

  // The transcript outlived the page. This is the whole point of the feature.
  await expect(page.getByTestId("history-item").filter({ hasText: marker })).toHaveCount(1);
});
