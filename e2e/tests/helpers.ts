import { expect, type Page } from "@playwright/test";

/**
 * Wait until React has attached on the client.
 *
 * **The one thing worth waiting for.** Nearly every page here is a `"use client"` component that
 * still server-renders, so buttons arrive in the HTML — visible, enabled, carrying their
 * `data-testid` — before `onClick` exists. A click in that gap is dropped silently, and the
 * failure surfaces on the *next* assertion as a missing element, which reads like a broken
 * feature rather than a race. It moved to a different test on every run depending on how loaded
 * the machine was.
 *
 * Nothing already in the DOM distinguishes "rendered" from "interactive": the canvas toolbar
 * being visible, `toBeVisible()`, `toBeEnabled()` — all true of server-rendered markup. So the
 * app sets `<html data-hydrated>` in an effect (`components/hydration-marker.tsx`) and this waits
 * for it.
 *
 * Call once after each navigation, before the first interaction. It replaces the alternative of
 * retrying every click at ~50 call sites, which would have been the same bug fixed fifty times.
 */
export async function waitForHydration(page: Page, timeout = 15_000) {
  await page.waitForFunction(
    () => document.documentElement.dataset.hydrated === "true",
    undefined,
    { timeout },
  );
}

/**
 * Go to `path`, click through the dev sign-in if it appears, and wait for hydration.
 *
 * The sign-in button is itself server-rendered inside a `<form>`, so it survives an early click —
 * the form posts regardless of React. It's everything *after* the redirect that needs the wait.
 */
export async function signInAt(page: Page, path: string) {
  await page.goto(path);
  const devSignIn = page.getByTestId("dev-sign-in");
  if (await devSignIn.count()) {
    await devSignIn.click();
  }
  await waitForHydration(page);
}

/** Open the canvas and wait until its toolbar will actually respond. */
export async function openCanvas(page: Page) {
  await signInAt(page, "/canvas");
  await expect(page.getByTestId("canvas-toolbar")).toBeVisible();
}

/**
 * Add a node from the palette.
 *
 * No retry: `waitForHydration` has already established that clicks land. A retry here would be
 * actively wrong — re-clicking adds a *second* node whenever the first click was merely slow,
 * quietly changing the graph under test.
 */
export async function addNode(page: Page, kind: string) {
  await page.getByTestId(`add-${kind}`).click();
  await expect(page.getByTestId(`node-${kind}`)).toBeVisible();
}

/**
 * Wire one node's output to another's input, the way a user does.
 *
 * Adding a block no longer connects it to anything — blocks can be dropped anywhere, so "the
 * previous one" stopped meaning anything spatially and every connection is now drawn by hand.
 * Tests that need a working graph have to draw it.
 *
 * Uses raw mouse events rather than `dragAndDrop`: React Flow's connection handling is built on
 * pointer events and needs intermediate moves to register a drag at all, which the one-shot
 * helper doesn't produce.
 */
export async function connect(page: Page, fromKind: string, toKind: string) {
  const source = page
    .locator(`.react-flow__node:has([data-testid="node-${fromKind}"]) .react-flow__handle.source`)
    .first();
  const target = page
    .locator(`.react-flow__node:has([data-testid="node-${toKind}"]) .react-flow__handle.target`)
    .first();
  const s = await source.boundingBox();
  const t = await target.boundingBox();
  if (!s || !t) throw new Error(`connect(${fromKind} → ${toKind}): a handle was not visible`);

  await page.mouse.move(s.x + s.width / 2, s.y + s.height / 2);
  await page.mouse.down();
  await page.mouse.move(t.x + t.width / 2, t.y + t.height / 2, { steps: 12 });
  await page.mouse.up();
}

/** Where the nodes and the canvas viewport currently sit, in screen coordinates. */
async function geometry(page: Page) {
  return page.evaluate(() => {
    const pane = document.querySelector(".react-flow")!.getBoundingClientRect();
    const boxes = [...document.querySelectorAll(".react-flow__node")].map((n) =>
      n.getBoundingClientRect(),
    );
    if (!boxes.length) return null;
    return {
      pane: { x: pane.x, y: pane.y, w: pane.width, h: pane.height },
      content: {
        left: Math.min(...boxes.map((b) => b.left)),
        right: Math.max(...boxes.map((b) => b.right)),
        top: Math.min(...boxes.map((b) => b.top)),
        bottom: Math.max(...boxes.map((b) => b.bottom)),
      },
    };
  });
}

/**
 * Get every node on screen, so its handles can actually be clicked.
 *
 * Two things conspire against a freshly built chain. `fitView` fires once the first block exists
 * and zooms to the 2× maximum, and each new block is placed 240 units further right — so by the
 * third one the chain runs off the edge. The first version of `buildChain` silently produced 1
 * edge out of 2 for exactly this reason, which is the kind of failure that looks like a broken
 * feature.
 *
 * Zooms out with the app's own shortcut until the content fits, then pans with the hand tool —
 * both real user actions, rather than reaching into React Flow's store.
 */
async function bringIntoView(page: Page) {
  for (let i = 0; i < 8; i++) {
    const g = await geometry(page);
    if (!g) return;
    // Leave a margin so a handle sitting exactly on the edge is still comfortably clickable.
    if (g.content.right - g.content.left <= g.pane.w - 80) break;
    await page.keyboard.press("-");
    await page.waitForTimeout(220); // the zoom is animated; measuring mid-flight reads a stale box
  }

  const g = await geometry(page);
  if (!g) return;
  const dx = (g.pane.x + g.pane.w / 2) - (g.content.left + g.content.right) / 2;
  const dy = (g.pane.y + g.pane.h / 2) - (g.content.top + g.content.bottom) / 2;
  if (Math.abs(dx) < 2 && Math.abs(dy) < 2) return;

  // The hand tool: with the arrow, a left-drag on the pane draws a selection box instead.
  await page.keyboard.press("h");
  const from = { x: g.pane.x + 20, y: g.pane.y + g.pane.h - 20 };
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(from.x + dx, from.y + dy, { steps: 10 });
  await page.mouse.up();
  await page.keyboard.press("v");
}

/**
 * Switch the right panel to its Code tab, opening the panel first if it is closed.
 *
 * The panel is no longer always on screen: it opens when you click a node and closes when you
 * click empty canvas, so an unselected canvas isn't 320px of "Select a node to edit its
 * properties". That means `toggle-code` may not be mounted, and every test that reads generated
 * code has to get the panel open first.
 */
export async function openCode(page: Page) {
  if (!(await page.getByTestId("toggle-code").count())) {
    await page.getByTestId("toggle-right-panel").click();
  }
  await page.getByTestId("toggle-code").click();
}

/** Add each block in order and wire them into a straight chain. The common shape by far. */
export async function buildChain(page: Page, kinds: string[]) {
  for (const kind of kinds) await addNode(page, kind);
  await bringIntoView(page);
  for (let i = 0; i < kinds.length - 1; i++) await connect(page, kinds[i], kinds[i + 1]);
  await expect(page.locator(".react-flow__edge")).toHaveCount(kinds.length - 1);
}
