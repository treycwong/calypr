import { expect, type Page, test } from "@playwright/test";

import { buildChain, openCanvas, signInAt } from "./helpers";

// The sidebar panels moved to a shared tile language: Connectors and Models are grids of cards,
// the assistant opens on an intro with example prompts, Media tiles audio the way it already
// tiled images, and wires take the colour of the block they leave. These cover the behaviour of
// each; the panels' underlying CRUD is covered by the API tests and phase-settings.

/** Serve a mixed media library, so the grid renders without a database behind it.
 *
 *  Deliberately alternating kinds: images and audio used to render in two stacked grids, so the
 *  bug only shows when both are present and the API's order interleaves them.
 */
const PIXEL =
  "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7";

async function withAssets(page: Page) {
  const at = new Date().toISOString();
  await page.route("**/api/assets*", async (route) => {
    await route.fulfill({
      json: {
        items: [
          { id: "i1", kind: "image", url: PIXEL, caption: "Create a kodak street", model: "gpt-image-2", created_at: at },
          { id: "a1", kind: "audio", url: "data:audio/mpeg;base64,SUQzAw==", caption: "In a quaint village, nestled between two hills", model: "gpt-4o-mini-tts", created_at: at },
          { id: "i2", kind: "image", url: PIXEL, caption: "Create a film street", model: "gpt-image-2", created_at: at },
          { id: "a2", kind: "audio", url: "data:audio/mpeg;base64,SUQzAw==", caption: "The second recording", model: "gpt-4o-mini-tts", created_at: at },
        ],
        next_cursor: null,
      },
    });
  });
}

test("images and audio share one grid, in API order", async ({ page }) => {
  await withAssets(page);
  await signInAt(page, "/canvas");
  await page.getByTestId("toggle-media").click();

  const items = page.getByTestId("media-item");
  await expect(items).toHaveCount(4);

  const boxes = await items.evaluateAll((els) =>
    els.map((e) => {
      const r = e.getBoundingClientRect();
      return { x: r.x, y: r.y, w: r.width, h: r.height };
    }),
  );

  // Every cell is the same size regardless of kind — that is what lets them tile together.
  for (const b of boxes) {
    expect(Math.abs(b.w - boxes[0].w)).toBeLessThan(1);
    expect(Math.abs(b.h - boxes[0].h)).toBeLessThan(1);
  }
  // An image and an audio clip share the first row, and the next pair sits below. Two stacked
  // grids put every audio item below every image, which is the break this fixed.
  expect(Math.abs(boxes[0].y - boxes[1].y)).toBeLessThan(2);
  expect(boxes[1].x).toBeGreaterThan(boxes[0].x);
  expect(boxes[2].y).toBeGreaterThan(boxes[0].y);

  // The caption identifies the clip — for audio it is the only thing telling two apart.
  await expect(page.getByTestId("media-caption").nth(1)).toContainText("quaint village");
});

test("every media tile has one menu carrying Download, Open and Delete", async ({ page }) => {
  await withAssets(page);
  await signInAt(page, "/canvas");
  await page.getByTestId("toggle-media").click();

  // One menu per tile, and no loose icon row: the three actions used to sit on the face of every
  // image thumbnail, and audio had only Delete.
  await expect(page.getByTestId("media-menu")).toHaveCount(4);

  // The audio tile has no inline player any more — Open hands it to the browser instead.
  await expect(page.locator("audio")).toHaveCount(0);

  // Same menu on an audio tile as on an image one.
  await page.getByTestId("media-menu").nth(1).click();
  await expect(page.getByTestId("media-download")).toBeVisible();
  await expect(page.getByTestId("media-open")).toBeVisible();
  await expect(page.getByTestId("media-delete")).toBeVisible();
});

test("the assistant opens on an intro with example prompts", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("toggle-assistant").click();

  const intro = page.getByTestId("assistant-intro");
  await expect(intro).toBeVisible();
  await expect(intro).toContainText("Describe the agent you want");

  const examples = page.getByTestId("assistant-example");
  await expect(examples).toHaveCount(4);
  await expect(examples.first()).toHaveText("Create a RAG chatbot for my website");

  // Picking one sends it as a message rather than only filling the composer, and the intro is
  // replaced by the conversation.
  await examples.first().click();
  await expect(page.getByText("Create a RAG chatbot for my website")).toBeVisible();
  await expect(intro).toHaveCount(0);
});

test("the connector tiles are the same shape as the Blocks tiles", async ({ page }) => {
  await openCanvas(page);
  const block = await page.getByTestId("add-input").boundingBox();

  await page.getByTestId("tab-connectors").click();
  // Every sidebar grid shares one tile, so a provider card is the same size as a block.
  const provider = await page.getByTestId("key-provider-openai").boundingBox();
  expect(Math.abs(block!.width - provider!.width)).toBeLessThan(1);
  expect(Math.abs(block!.height - provider!.height)).toBeLessThan(1);
});

test("the Blocks and Templates grids are the same width", async ({ page }) => {
  await openCanvas(page);

  // A visible scrollbar used to take ~15px of layout width from whichever panel overflowed, so
  // its two columns came out narrower than the other panel's. Both scroll; neither reserves a
  // gutter.
  const block = await page.getByTestId("add-input").boundingBox();
  await page.getByTestId("tab-templates").click();
  const template = await page.getByTestId("templates-panel").getByRole("button").first().boundingBox();

  expect(block).not.toBeNull();
  expect(template).not.toBeNull();
  expect(Math.abs(block!.width - template!.width)).toBeLessThan(1);
});

test("the key dialog names the key on file without revealing it", async ({ page }) => {
  // `key_hint` is the last 4 characters, stored in the clear at write time. The real key is
  // Fernet ciphertext that the API has never been able to return, so there is nothing to unhide.
  await page.route("**/api/provider-keys", async (route) => {
    await route.fulfill({
      json: [
        { provider: "openai", has_key: true, key_hint: "wxyz" },
        { provider: "anthropic", has_key: false, key_hint: null },
      ],
    });
  });
  await signInAt(page, "/canvas");
  await page.getByTestId("tab-connectors").click();

  // Only a keyed provider says anything — "No key" under every other tile was the grid repeating
  // the absence of news.
  await expect(page.getByTestId("key-onfile-openai")).toBeVisible();
  await expect(page.getByTestId("key-providers")).not.toContainText("No key");

  await page.getByTestId("key-provider-openai").click();
  await expect(page.getByTestId("key-masked")).toContainText("wxyz");

  // The eye reveals what *you* type, not what is stored.
  const input = page.getByTestId("key-input");
  await expect(input).toHaveAttribute("type", "password");
  await input.fill("sk-typed-by-me");
  await page.getByTestId("key-reveal").click();
  await expect(input).toHaveAttribute("type", "text");
  await expect(input).toHaveValue("sk-typed-by-me");
});

test("disconnecting an account asks first", async ({ page }) => {
  // Served rather than assumed: the suite's workspace has no connected accounts, and a
  // conditional skip would mean this path is never actually exercised in CI.
  await page.route("**/api/connectors", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      json: [
        { id: "c1", kind: "github", name: "GitHub", url: null },
        { id: "c2", kind: "notion", name: "Tracey Wong", url: null },
      ],
    });
  });
  await signInAt(page, "/canvas");
  await page.getByTestId("tab-connectors").click();

  // The card is the mark and a status — the account name moved to the tooltip, so it must NOT
  // appear as text on the card.
  const card = page.getByTestId("connector-card-github");
  await expect(card).toContainText("Connected");
  await expect(card).not.toContainText("GitHub");
  await expect(card).toHaveAttribute("title", /GitHub/);

  await page.getByTestId("connector-menu-github").click();
  // A token app can be handed a new credential; an OAuth app can only be re-authorised.
  await expect(page.getByTestId("connector-credential-github")).toHaveText("API key");
  await page.getByTestId("connector-disconnect-github").click();

  const confirm = page.getByTestId("connector-disconnect-confirm");
  await expect(confirm).toBeVisible();
  await expect(confirm).toContainText("Disconnect this account?");
  // Cancel backs out, leaving the account connected.
  await confirm.getByRole("button", { name: "Cancel" }).click();
  await expect(confirm).toHaveCount(0);
  await expect(card).toBeVisible();
});

test("an OAuth account is offered Reconnect, not an API key", async ({ page }) => {
  await page.route("**/api/connectors", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({ json: [{ id: "c2", kind: "notion", name: "Tracey Wong", url: null }] });
  });
  await signInAt(page, "/canvas");
  await page.getByTestId("tab-connectors").click();

  await page.getByTestId("connector-menu-notion").click();
  // Notion holds an OAuth grant, not a key — there is nothing to paste, so the only way to
  // change what we hold is to walk its consent screen again.
  await expect(page.getByTestId("connector-credential-notion")).toHaveText("Reconnect");
});

test("Add connection sits on the section header, not in the grid", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("tab-connectors").click();

  const add = page.getByTestId("connection-add-open");
  await expect(add).toBeVisible();
  // It is aligned with the heading rather than being another card below it.
  const heading = page.getByText("Connected accounts", { exact: true });
  const a = await add.boundingBox();
  const h = await heading.boundingBox();
  expect(Math.abs((a!.y + a!.height / 2) - (h!.y + h!.height / 2))).toBeLessThan(6);
  await expect(page.getByTestId("connected-accounts")).not.toContainText("Add");
});

test("wires take the colour of the block they leave", async ({ page }) => {
  await openCanvas(page);

  await buildChain(page, ["input", "image", "output"]);

  const strokes = await page
    .locator(".react-flow__edge-path")
    .evaluateAll((els) => els.map((e) => (e as SVGElement).style.stroke));

  // sky-500 leaving Input, pink-500 leaving Image — the source block's colour, not the target's.
  // These were the -300 pastels until they proved too washed out to trace across a busy canvas.
  expect(strokes[0]).toBe("rgb(14, 165, 233)");
  expect(strokes[1]).toBe("rgb(236, 72, 153)");
});
