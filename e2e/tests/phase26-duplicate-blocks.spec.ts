import { expect, test } from "@playwright/test";

import { addNode, buildChain, openCanvas } from "./helpers";

// Duplicating blocks: ⌘/Ctrl+D on the selection, and ⌘/Ctrl+C / ⌘/Ctrl+V through the real system
// clipboard (so a block can be carried between projects and tabs).
//
// `ControlOrMeta` is Playwright's platform-correct modifier — the same spec runs on a mac laptop
// and a Linux CI box without branching on `process.platform`.

const MOD = "ControlOrMeta";

test("duplicating a block copies its settings, not its run output", async ({ page }) => {
  await openCanvas(page);
  await addNode(page, "image");
  await page.getByTestId("node-image").click();

  // A setting worth carrying across — if the copy shared config by reference rather than value,
  // editing one would change the other, and this is where that would show up.
  const style = page.getByTestId("config-panel").locator("#cfg-style");
  await style.fill("MARKER-STYLE");

  // Back to the canvas first: ⌘D is deliberately inert while a field has focus, so that typing a
  // prompt and reaching for "duplicate" can't act on a block you aren't looking at.
  await page.getByTestId("node-image").click();
  await page.keyboard.press(`${MOD}+d`);
  await expect(page.locator(".react-flow__node")).toHaveCount(2);

  // The copy is the new selection, so the properties panel is already showing it.
  await expect(style).toHaveValue("MARKER-STYLE");

  // Editing the copy must not reach back into the original.
  await style.fill("CHANGED");
  await page.locator(".react-flow__node").first().click();
  await expect(style).toHaveValue("MARKER-STYLE");
});

test("duplicating a selection keeps the wires inside it and drops the ones leaving it", async ({
  page,
}) => {
  await openCanvas(page);
  await buildChain(page, ["input", "image", "output"]);
  await expect(page.locator("g.react-flow__edge")).toHaveCount(2);

  // Marquee the first two blocks only.
  const input = await page.getByTestId("node-input").boundingBox();
  const image = await page.getByTestId("node-image").boundingBox();
  await page.mouse.move(input!.x - 20, input!.y - 20);
  await page.mouse.down();
  await page.mouse.move(image!.x + image!.width + 10, image!.y + image!.height + 10, { steps: 8 });
  await page.mouse.up();
  await expect(page.locator(".react-flow__node.selected")).toHaveCount(2);

  await page.keyboard.press(`${MOD}+d`);
  await expect(page.locator(".react-flow__node")).toHaveCount(5);
  // Three edges, not four: the Input → Image wire came along because both ends were copied, and
  // the Image → Output wire did not, because Output stayed behind. A copied wire that silently
  // re-pointed at the *original* Output would look connected and feed the wrong branch.
  await expect(page.locator("g.react-flow__edge")).toHaveCount(3);
});

test("a duplicate is undoable", async ({ page }) => {
  await openCanvas(page);
  await addNode(page, "agent");
  await page.getByTestId("node-agent").click();
  await page.keyboard.press(`${MOD}+d`);
  await expect(page.locator(".react-flow__node")).toHaveCount(2);

  await page.keyboard.press(`${MOD}+z`);
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
});

test("copy and paste go through the system clipboard, and repeat pastes fan out", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await openCanvas(page);
  await addNode(page, "image");
  await page.getByTestId("node-image").click();

  await page.keyboard.press(`${MOD}+c`);
  await page.keyboard.press(`${MOD}+v`);
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await page.keyboard.press(`${MOD}+v`);
  await expect(page.locator(".react-flow__node")).toHaveCount(3);

  // Each paste steps further from the original rather than stacking on the last one.
  const boxes = await page.locator(".react-flow__node").evaluateAll((els) =>
    els.map((el) => Math.round(el.getBoundingClientRect().x)),
  );
  expect(new Set(boxes).size).toBe(3);
});

test("pasting into a text field does not add blocks to the canvas", async ({ page, context }) => {
  // The guard that makes the feature safe to leave on: the canvas listens for `paste` on the
  // window, so without it every paste into the config panel or the chat would also drop a block
  // onto the graph.
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await openCanvas(page);
  await addNode(page, "image");
  await page.getByTestId("node-image").click();
  await page.keyboard.press(`${MOD}+c`);

  const style = page.getByTestId("config-panel").locator("#cfg-style");
  await style.click();
  await page.keyboard.press(`${MOD}+v`);

  await expect(page.locator(".react-flow__node")).toHaveCount(1);
});

test("duplicate is inert while typing, and never reaches the browser's bookmark dialog", async ({
  page,
}) => {
  await openCanvas(page);
  await addNode(page, "image");
  await page.getByTestId("node-image").click();

  const style = page.getByTestId("config-panel").locator("#cfg-style");
  await style.click();
  await style.type("a prompt");
  // Swallowed rather than passed through: there is no useful native ⌘D in a textarea, so letting
  // it escape means a bookmark prompt over the canvas.
  const prevented = await page.evaluate(() => {
    const el = document.querySelector("#cfg-style") as HTMLElement;
    el.focus();
    const ev = new KeyboardEvent("keydown", {
      key: "d",
      metaKey: true,
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
    });
    // Dispatched on the field, not on window: `e.target` is what the guard reads, and a real
    // keypress in a textarea targets the textarea and bubbles up from there.
    el.dispatchEvent(ev);
    return ev.defaultPrevented;
  });
  expect(prevented).toBe(true);
  // …and it did not duplicate anything.
  await expect(page.locator(".react-flow__node")).toHaveCount(1);
});
