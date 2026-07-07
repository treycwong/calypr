import { expect, test } from "@playwright/test";

// Phase 9 gate (AI-ASSISTANT-SPEC.md §10): open the canvas, ask the AI assistant for a RAG
// chatbot. The proposed graph previews live on the canvas (wired Input → Retriever → Agent →
// Output) with Apply/Discard controls; Apply commits it. Then "Try it" streams a reply, the
// Code tab shows Python containing a retriever, and "Undo" reverts to the (empty) prior graph.
// Keyless: the assistant's fake path maps "rag" → the RAG template and forces the fake model,
// so the gate needs no API key and no database.
test("prompt the assistant to build a RAG chatbot, approve, then undo", async ({ page }) => {
  await page.goto("/canvas");
  await page.getByTestId("dev-sign-in").click();
  await expect(page).toHaveURL(/\/canvas/);
  await expect(page.locator(".react-flow__controls")).toBeVisible();

  // Open the AI assistant rail panel and send a prompt.
  await page.getByTestId("toggle-assistant").click();
  await expect(page.getByTestId("assistant-panel")).toBeVisible();
  await page
    .getByTestId("assistant-input")
    .fill("I would like a RAG chatbot for my website");
  await page.getByTestId("assistant-send").click();

  // The graph previews live on the canvas (Input → Retriever → Agent → Output), with the
  // Apply control awaiting approval.
  await expect(page.getByTestId("assistant-apply")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("node-retriever")).toBeVisible();
  await expect(page.getByTestId("node-input")).toBeVisible();
  await expect(page.getByTestId("node-agent")).toBeVisible();
  await expect(page.getByTestId("node-output")).toBeVisible();

  // Approve → the preview is committed.
  await page.getByTestId("assistant-apply").click();
  await expect(page.getByTestId("node-retriever")).toBeVisible();

  // "Try it" runs the generated graph on the fake model and streams a reply.
  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("chat-input").fill("hello rag");
  await page.getByTestId("chat-send").click();
  await expect(page.getByTestId("msg-assistant").last()).toContainText("Echo: hello rag", {
    timeout: 15_000,
  });

  // Stop the playground and open the Code tab: the generated Python grounds on a retriever.
  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("toggle-code").click();
  await expect(page.getByTestId("code-output")).toContainText("retriev", {
    timeout: 15_000,
  });

  // "Undo" reverts to the pre-apply (empty) canvas.
  await page.getByTestId("assistant-restore").click();
  await expect(page.getByTestId("node-retriever")).toHaveCount(0);
  await expect(page.getByTestId("node-agent")).toHaveCount(0);
});
