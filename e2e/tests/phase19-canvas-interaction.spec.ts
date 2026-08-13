import { expect, test } from "@playwright/test";

import { openCanvas, openCode, signInAt } from "./helpers";

// Blocks are dragged onto the canvas and wired by hand; the browser tab is named after the
// project; and a selected node reads as selected rather than as running.

test("a block can be dragged from the palette onto the canvas", async ({ page }) => {
  await openCanvas(page);

  await page.getByTestId("add-agent").dragTo(page.locator(".react-flow__pane"), {
    targetPosition: { x: 200, y: 220 },
  });
  await expect(page.getByTestId("node-agent")).toBeVisible();

  // Dropped where it was released, not appended to a queue: a second block dropped lower down
  // lands lower down.
  await page.getByTestId("add-output").dragTo(page.locator(".react-flow__pane"), {
    targetPosition: { x: 200, y: 420 },
  });
  const agent = await page.getByTestId("node-agent").boundingBox();
  const output = await page.getByTestId("node-output").boundingBox();
  expect(output!.y).toBeGreaterThan(agent!.y);
});

test("adding blocks wires nothing — connections are the user's", async ({ page }) => {
  await openCanvas(page);

  await page.getByTestId("add-input").click();
  await page.getByTestId("add-agent").click();
  await expect(page.getByTestId("node-agent")).toBeVisible();

  // Two blocks, no edge. Auto-linking guessed a straight chain, which was wrong the moment you
  // wanted a branch — and meaningless once blocks can be dropped anywhere.
  await expect(page.locator(".react-flow__edge")).toHaveCount(0);
  // ...and the caption that used to explain the guess is gone with it.
  await expect(page.getByTestId("add-input").locator("..")).not.toContainText("links it after");
});

test("the browser tab is named after the project, and follows a rename", async ({ page }) => {
  await openCanvas(page);

  await expect(page).toHaveTitle(/Untitled Agent/);

  await page.getByTestId("agent-name").fill("Street Photography");
  // Client state, so the title tracks the edit itself — no save, no navigation.
  await expect(page).toHaveTitle(/^Street Photography · Calypr$/);
});

test("a selected node reads as selected, not as running", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("add-agent").click();

  const node = page.getByTestId("node-agent");
  await node.click();

  // Polled, not sampled once: the card carries a CSS `transition`, so reading the moment after
  // the click catches the colours mid-interpolation — still showing the *unselected* values,
  // which reads exactly like the feature being broken.
  //
  // Tailwind v4 emits `oklab(…)`, so this asserts on the parsed components rather than matching
  // an "rgb(…)" string that would never appear.
  const settled = async () =>
    node.evaluate((el) => {
      const c = getComputedStyle(el);
      const alpha = (v: string) => Number(v.match(/\/\s*([\d.]+)\s*\)/)?.[1] ?? "1");
      // Chrome serialises these in whichever space the value was authored in: `oklab()` for a
      // Tailwind `color-mix`, plain `lab()` for a literal palette colour like `neutral-700`.
      // Their lightness channels use different ranges (0–1 vs 0–100), so normalise to 0–1.
      const lightness = (v: string) => {
        const ok = v.match(/oklab\(([\d.]+)/);
        if (ok) return Number(ok[1]);
        const lab = v.match(/\blab\(([\d.]+)/);
        return lab ? Number(lab[1]) / 100 : 0;
      };
      return {
        borderAlpha: alpha(c.borderColor),
        borderLight: lightness(c.borderColor),
        bgAlpha: alpha(c.backgroundColor),
        bgLight: lightness(c.backgroundColor),
      };
    });

  // Poll on the border's *alpha*, not its lightness: the idle border is white at 10% and the
  // selected one white at 60%, so lightness is already satisfied before the transition starts
  // and polling on it would pass instantly against an unselected node.
  await expect.poll(async () => (await settled()).borderAlpha).toBeGreaterThan(0.5);

  const s = await settled();
  expect(s.borderLight).toBeGreaterThan(0.9); // white-grey, not cyan (cyan-400 sits near 0.79)
  // The fill is a solid grey, lighter than the unselected card but nowhere near white — the
  // *next* test is the one that pins its opacity.
  expect(s.bgLight).toBeGreaterThan(0.2);
  expect(s.bgLight).toBeLessThan(0.6);
});

test("a selected node is opaque, so wires do not show through it", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("add-agent").click();
  const node = page.getByTestId("node-agent");
  await node.click();

  // A translucent wash let the wires behind the card show straight through it, which made a
  // selected node in a busy graph harder to read rather than easier.
  await expect
    .poll(async () =>
      node.evaluate((el) => {
        const bg = getComputedStyle(el).backgroundColor;
        // Alpha is only serialised when it is < 1, so its absence *is* opacity.
        return Number(bg.match(/\/\s*([\d.]+)\s*\)/)?.[1] ?? "1");
      }),
    )
    .toBe(1);
});

test("the Saved prompts tab is present and says it is coming", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("tab-prompts").click();

  const panel = page.getByTestId("prompts-panel");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("Coming soon");
  // No dead controls: the panel says what it will be rather than mocking up a feature that does
  // not exist yet.
  await expect(panel.getByRole("button")).toHaveCount(0);
});

test("the AI assistant rail icon is a robot, and no divider precedes it", async ({ page }) => {
  await openCanvas(page);

  // lucide renders its name onto the svg as a class, which is the only stable handle on
  // *which* glyph is drawn.
  const icon = page.getByTestId("toggle-assistant").locator("svg");
  await expect(icon).toHaveClass(/lucide-bot-message-square/);

  // The rail is one uninterrupted group now.
  await expect(page.locator("aside .bg-border")).toHaveCount(0);
});

test("project cards show the shape of their graph", async ({ page }) => {
  // Served, so the card's rendering is tested rather than whatever the dev workspace happens to
  // hold. `preview` is the compact projection the list endpoint adds — types, positions, edges.
  await page.route("**/api/agents", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      json: [
        {
          id: "a1",
          name: "Street Photography",
          updated_at: new Date().toISOString(),
          preview: {
            nodes: [
              { type: "input", x: 0, y: 0 },
              { type: "image", x: 240, y: 0 },
              { type: "output", x: 480, y: 0 },
            ],
            edges: [
              [0, 1],
              [1, 2],
            ],
          },
        },
        { id: "a2", name: "Blank", updated_at: new Date().toISOString(), preview: null },
      ],
    });
  });
  await signInAt(page, "/dashboard");

  const cards = page.getByTestId("project-card");
  await expect(cards).toHaveCount(2);

  // Square, per the reference — the thumbnail is the card's main surface, name underneath.
  const thumb = page.getByTestId("graph-thumb").first();
  const box = await thumb.boundingBox();
  expect(Math.abs(box!.width - box!.height)).toBeLessThan(2);

  // Two wires, coloured by the block they leave: sky out of Input, pink out of Image.
  const strokes = await page
    .getByTestId("graph-thumb")
    .first()
    .locator("line")
    .evaluateAll((els) => els.map((e) => e.getAttribute("stroke")));
  expect(strokes).toEqual(["#0ea5e9", "#ec4899"]);

  // The nodes are the blocks themselves — a chip per block carrying its own icon — not dots.
  const types = await page
    .getByTestId("graph-thumb")
    .first()
    .locator("[data-node-type]")
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-node-type")));
  expect(types).toEqual(["input", "image", "output"]);

  // A project saved with an empty canvas says so rather than rendering a blank square.
  await expect(page.getByTestId("graph-thumb-empty")).toBeVisible();
});

test("a thumbnail keeps the graph's proportions", async ({ page }) => {
  // A wide, shallow graph — the common shape. Scaling each axis to fill the square independently
  // turned this 74px rise across a 500px span into a mountain; the thumbnail has to be the same
  // shape as the canvas it stands for.
  await page.route("**/api/agents", async (route) => {
    if (route.request().method() !== "GET") return route.fallback();
    await route.fulfill({
      json: [
        {
          id: "a1",
          name: "Wide and shallow",
          updated_at: new Date().toISOString(),
          preview: {
            nodes: [
              { type: "input", x: 68, y: 334 },
              { type: "image", x: 304, y: 260 },
              { type: "output", x: 565, y: 334 },
            ],
            edges: [
              [0, 1],
              [1, 2],
            ],
          },
        },
      ],
    });
  });
  await signInAt(page, "/dashboard");

  const chips = page.getByTestId("graph-thumb").first().locator("[data-node-type]");
  const boxes = await chips.evaluateAll((els) =>
    els.map((e) => {
      const r = e.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    }),
  );

  // The rise must stay a small fraction of the run, as it is in the source graph (74 / 497).
  const run = Math.abs(boxes[2].x - boxes[0].x);
  const rise = Math.abs(boxes[0].y - boxes[1].y);
  expect(run).toBeGreaterThan(0);
  expect(rise / run).toBeLessThan(0.35);
});

test("the right panel follows the selection", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("add-agent").click();

  // Nothing selected, so no panel — it used to be 320px of "Select a node to edit its properties."
  await expect(page.getByTestId("right-panel")).toHaveCount(0);

  await page.getByTestId("node-agent").click();
  await expect(page.getByTestId("right-panel")).toBeVisible();
  await expect(page.getByTestId("config-panel")).toBeVisible();

  // Clicking empty canvas puts it away again.
  await page.locator(".react-flow__pane").click({ position: { x: 40, y: 260 } });
  await expect(page.getByTestId("right-panel")).toHaveCount(0);
});

test("the Code tab survives a click on the canvas", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("add-agent").click();

  // The header toggle is the way in with nothing selected.
  await openCode(page);
  await expect(page.getByTestId("code-panel")).toBeVisible();

  // Code isn't about the selection, so deselecting must not close it mid-read.
  await page.locator(".react-flow__pane").click({ position: { x: 40, y: 260 } });
  await expect(page.getByTestId("code-panel")).toBeVisible();
});

test("hiding the left panel leaves the graph where it was", async ({ page }) => {
  await openCanvas(page);
  await page.getByTestId("add-input").click();
  const node = page.getByTestId("node-input");
  const before = await node.boundingBox();

  // The canvas is a flex child, so collapsing the panel widens it leftwards — without the
  // viewport compensation every node slid 240px across the screen.
  await page.getByTestId("hide-panel").click();
  await expect(page.getByTestId("add-input")).toHaveCount(0);
  const afterHide = await node.boundingBox();
  expect(Math.abs(afterHide!.x - before!.x)).toBeLessThan(2);

  await page.getByTestId("tab-blocks").click();
  await expect(page.getByTestId("add-input")).toBeVisible();
  const afterShow = await node.boundingBox();
  expect(Math.abs(afterShow!.x - before!.x)).toBeLessThan(2);
});

test("the rail panel is 240px, and Templates headings match the Connectors ones", async ({
  page,
}) => {
  await openCanvas(page);
  const panel = page.locator("aside").filter({ has: page.getByTestId("add-input") });
  expect((await panel.boundingBox())!.width).toBe(240);

  await page.getByTestId("tab-templates").click();
  const heading = page
    .getByTestId("templates-panel")
    .locator("div", { hasText: /^Frameworks$/ })
    .first();
  await expect(heading).toHaveCSS("text-transform", "uppercase");
});
