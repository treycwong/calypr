import { type Page, expect, test } from "@playwright/test";

import { openCanvas } from "./helpers";

// Generated media used to be a dead end in the chat: an image you could only squint at, and a 3D
// model that rendered as a bare link to a file the browser cannot display. Both now open a full
// viewer, and it is the *same* viewer either way.
//
// The fake model echoes whatever it is sent, so both cases are driven by typing markdown into the
// chat — no keys, no provider, and it tests the exact path a real run takes: the node streams
// markdown, `<Markdown>` renders it, and these components take over.

async function echoTemplate(page: Page, message: string) {
  await openCanvas(page);
  await page.getByTestId("tab-templates").click();
  await page
    .getByTestId("templates-panel")
    .getByRole("button", { name: "Image Finder", exact: true })
    .click();
  await page.getByTestId("template-apply").click();
  await page.getByTestId("node-agent").click();
  await page.getByTestId("cfg-model").selectOption("fake");
  await page.getByTestId("toggle-playground").click();
  await page.getByTestId("chat-input").fill(message);
  await page.getByTestId("chat-send").click();
}

const PHOTO =
  "https://images.unsplash.com/photo-1496588152823-86ff7695e68f?crop=entropy&fm=jpg&w=64";

test("clicking a generated image opens it full size", async ({ page }) => {
  await echoTemplate(page, `![a foggy forest](${PHOTO})`);

  const open = page.getByTestId("msg-assistant").last().getByTestId("image-open");
  await expect(open).toBeVisible({ timeout: 15_000 });
  await open.click();

  const viewer = page.getByTestId("media-viewer");
  await expect(viewer).toBeVisible();
  await expect(viewer.getByTestId("media-viewer-image")).toHaveAttribute("src", PHOTO);
  // The caption is the alt text, which is also the download filename and the accessible name.
  await expect(viewer).toContainText("a foggy forest");

  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
});

test("the image download control still fires after the lightbox was added", async ({ page }) => {
  // The image became a <button> to open the viewer, and the download control sits directly
  // beneath it. This is the regression that change could plausibly cause.
  await echoTemplate(page, `![a foggy forest](${PHOTO})`);
  const bubble = page.getByTestId("msg-assistant").last();
  await expect(bubble.getByTestId("image-download")).toBeVisible({ timeout: 15_000 });

  const download = page.waitForEvent("download");
  await bubble.getByTestId("image-download").click();
  expect((await download).suggestedFilename()).toContain("foggy");
  // Downloading must not have opened the viewer — the two controls are adjacent.
  await expect(page.getByTestId("media-viewer")).toHaveCount(0);
});

test("a .glb link renders as a model card, not a bare anchor", async ({ page }) => {
  const glb = "https://store.public.blob.vercel-storage.com/runs/glb/abc123.glb";
  await echoTemplate(page, `[⬇ Download model.glb](${glb})`);

  const bubble = page.getByTestId("msg-assistant").last();
  await expect(bubble.getByTestId("mesh-open")).toBeVisible({ timeout: 15_000 });
  // The whole point: it is not the plain <a> every other link gets.
  await expect(bubble.locator(`a[href="${glb}"]`)).toHaveCount(0);

  await bubble.getByTestId("mesh-open").click();
  const viewer = page.getByTestId("media-viewer");
  await expect(viewer).toBeVisible();

  // The 3D chunk is fetched on demand here. Headless Chromium may or may not give it WebGL, so
  // assert on the contract rather than the renderer: either the element mounts, or the honest
  // fallback tells the user to use the download link. An empty box is the failure.
  const mounted = viewer.getByTestId("model-viewer");
  await expect(mounted.or(viewer.getByTestId("model-viewer-failed"))).toBeVisible({
    timeout: 20_000,
  });

  // …and if it mounted, it must actually have been pointed at the file. React sets unknown values
  // on a custom element as a *property*, and model-viewer loads only from the `src` **attribute** —
  // so `<model-viewer src={…}>` mounts a permanently empty box that reports itself as loaded.
  // Asserting on presence alone let exactly that ship; asserting the attribute is deterministic
  // and needs no network.
  if (await mounted.count()) {
    await expect(mounted).toHaveAttribute("src", glb);
    // Eager, or it never fetches: model-viewer's default `lazy` waits on an IntersectionObserver
    // that never fires inside a portalled dialog. Both attributes are set by hand for the same
    // reason — React writes unknown values on a custom element as properties, which this element
    // does not reliably act on.
    await expect(mounted).toHaveAttribute("loading", "eager");
  }
});

test("an ordinary link is still an ordinary link", async ({ page }) => {
  // The .glb branch lives inside the generic link alternative, so it is one bad regex away from
  // eating every link in the chat.
  const url = "https://example.com/notes/model.glb.txt";
  await echoTemplate(page, `[my notes](${url})`);
  const bubble = page.getByTestId("msg-assistant").last();
  await expect(bubble.locator(`a[href="${url}"]`)).toBeVisible({ timeout: 15_000 });
  await expect(bubble.getByTestId("mesh-open")).toHaveCount(0);
});
