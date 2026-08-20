import { expect, test } from "@playwright/test";

import { buildChain, signInAt } from "./helpers";

// Study cards (STUDY-MODE §1): an agent emits ```calypr-card fences, and the chat renders them
// as interactive, scored cards — on the canvas and on a public share link alike.
//
// The card text has to be byte-exact for this gate, so it comes from a **Custom Code** node
// rather than from a real model. It is wired *before* the Agent, not after: only an Agent streams
// `token` events, so a graph that ends at a Code node renders nothing in the chat. The Code node
// therefore rewrites the user turn, and the keyless `fake` model echoes it back as a stream.

// A function body over `state`, typed into the Code node. The `\n` sequences are Python escapes
// (they reach the textarea literally), so the fences land on their own lines as the protocol
// requires.
const FENCE = "```";
const QUIZ =
  '{"kind":"quiz","q":"2+2?","choices":["3","4","5"],"answer":1,"explain":"Two plus two is four."}';
const FLIP = '{"kind":"flashcard","front":"H2O","back":"water"}';

const EMIT_CARDS = [
  "quiz = '" + FENCE + "calypr-card\\n" + QUIZ + "\\n" + FENCE + "'",
  "flip = '" + FENCE + "calypr-card\\n" + FLIP + "\\n" + FENCE + "'",
  'return {"messages": [HumanMessage(content="Here we go.\\n\\n" + quiz + "\\n\\n" + flip)]}',
].join("\n");

test("study cards render, grade, and tally on a share link", async ({ page, browser }) => {
  await signInAt(page, "/canvas");
  await expect(page.getByTestId("canvas-toolbar")).toBeVisible();

  await buildChain(page, ["input", "code", "agent", "output"]);

  await page.getByTestId("node-code").click();
  await page.getByTestId("cfg-code").fill(EMIT_CARDS);
  await page.getByTestId("cfg-imports").fill("from langchain_core.messages import HumanMessage");

  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");
  await expect(page.getByTestId("cfg-model")).toHaveValue("fake");

  await page.getByTestId("agent-name").fill("Kanji Drill");
  await page.getByTestId("save-agent").click();
  await expect(page.getByTestId("save-msg")).toContainText("Saved");

  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/share") && r.request().method() === "POST"),
    page.getByTestId("share-agent").click(),
  ]);
  const { token } = (await res.json()) as { token: string };
  expect(token).toBeTruthy();

  // A logged-out learner opens the link.
  const anon = await browser.newContext();
  const anonPage = await anon.newPage();
  await anonPage.goto(`/s/${token}`);
  await expect(anonPage.locator("html[data-hydrated]")).toBeAttached();
  await expect(anonPage.getByTestId("share-agent-name")).toContainText("Kanji Drill");

  // Nothing about the project is study-flagged server-side — the chrome appears because cards
  // arrived, so before the first turn this is an ordinary chat.
  await expect(anonPage.getByTestId("score-strip")).toBeHidden();

  await anonPage.getByTestId("chat-input").fill("start");
  await anonPage.getByTestId("chat-send").click();

  await expect(anonPage.getByTestId("quiz-card")).toBeVisible({ timeout: 15_000 });
  await expect(anonPage.getByTestId("flash-card")).toBeVisible();
  await expect(anonPage.getByTestId("score-strip")).toBeVisible();
  await expect(anonPage.getByTestId("score-correct")).toHaveText("0");

  // Answer the quiz correctly (choice index 1) — the explanation is revealed and the tally moves.
  await anonPage.getByTestId("quiz-choice").nth(1).click();
  await expect(anonPage.getByTestId("quiz-explain")).toContainText("four");
  await expect(anonPage.getByTestId("score-correct")).toHaveText("1");

  // Re-answering a locked card must not inflate the tally.
  await anonPage.getByTestId("quiz-choice").nth(0).click({ force: true });
  await expect(anonPage.getByTestId("score-correct")).toHaveText("1");

  // Self-grade the flashcard: the grade buttons only exist once the back is revealed.
  await expect(anonPage.getByTestId("flash-got")).toBeHidden();
  await anonPage.getByTestId("flash-flip").click();
  await anonPage.getByTestId("flash-got").click();
  await expect(anonPage.getByTestId("score-correct")).toHaveText("2");

  // The tally survives a reload — it is keyed to the conversation in localStorage.
  await anonPage.reload();
  await expect(anonPage.locator("html[data-hydrated]")).toBeAttached();

  await anon.close();
});

test("a project without cards still renders as a plain chat", async ({ page, browser }) => {
  await signInAt(page, "/canvas");
  await expect(page.getByTestId("canvas-toolbar")).toBeVisible();

  await buildChain(page, ["input", "agent", "output"]);
  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");

  await page.getByTestId("agent-name").fill("Plain Bot");
  await page.getByTestId("save-agent").click();
  await expect(page.getByTestId("save-msg")).toContainText("Saved");

  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().includes("/share") && r.request().method() === "POST"),
    page.getByTestId("share-agent").click(),
  ]);
  const { token } = (await res.json()) as { token: string };

  const anon = await browser.newContext();
  const anonPage = await anon.newPage();
  await anonPage.goto(`/s/${token}`);
  await expect(anonPage.locator("html[data-hydrated]")).toBeAttached();
  await anonPage.getByTestId("chat-input").fill("hi there");
  await anonPage.getByTestId("chat-send").click();

  await expect(anonPage.getByTestId("msg-assistant").last()).toContainText("Echo: hi there", {
    timeout: 15_000,
  });
  // No cards ⇒ no study chrome. This is the regression guard for every existing share link.
  await expect(anonPage.getByTestId("score-strip")).toBeHidden();
  await expect(anonPage.getByTestId("study-intents")).toBeHidden();

  await anon.close();
});
