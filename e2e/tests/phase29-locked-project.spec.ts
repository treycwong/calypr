import { expect, test } from "@playwright/test";

import { signInAt, waitForHydration } from "./helpers";

// A project beyond the plan's cap after a downgrade is read-only. Saving it already 402'd, but
// the Playground went on accepting messages and starting runs — so the lock only ever stopped
// the cheap half. `locking.locked_run_message` refuses the run now; this covers the surface that
// says so *before* someone types a message and waits for a stream that ends in a billing error.
//
// The API decides `locked` (`GET /agents/{id}`), so the spec drives it from there rather than
// simulating a downgrade — caps aren't enforced without an internal key, so a genuinely locked
// project can't be reached here.

const AGENT_ID = "11111111-2222-3333-4444-555555555555";

/** Answer the canvas's project load with a saved agent, locked or not. */
async function openProject(
  page: import("@playwright/test").Page,
  locked: boolean,
  open: "playground" | "assistant" = "playground",
) {
  await page.route(`**/api/agents/${AGENT_ID}`, (route) =>
    route.fulfill({
      json: {
        id: AGENT_ID,
        name: "Downgraded project",
        locked,
        graph: {
          name: "Downgraded project",
          nodes: [{ id: "in", type: "input", config: {} }],
          edges: [],
        },
      },
    }),
  );
  // Sign in first, then navigate with the query: the dev sign-in posts and redirects, and the
  // redirect does not carry `?agent=` — landing on a blank canvas that passes half these
  // assertions by accident.
  await signInAt(page, "/canvas");
  await page.goto(`/canvas?agent=${AGENT_ID}`);
  await waitForHydration(page);
  await expect(page.getByTestId("agent-name")).toHaveValue("Downgraded project");
  if (open === "playground") await page.getByTestId("toggle-playground").click();
  else await page.getByTestId("toggle-assistant").click();
}

test.afterEach(async ({ page }) => {
  await page.unrouteAll({ behavior: "ignoreErrors" });
});

test("a locked project replaces the composer with an upgrade prompt", async ({ page }) => {
  await openProject(page, true);

  const notice = page.getByTestId("chat-locked");
  await expect(notice).toBeVisible();
  // Both exits, same as the dashboard banner: a lock that only says "upgrade" reads as a paywall
  // on the user's own work, and deleting down to the cap unlocks it for free.
  await expect(notice).toContainText("Nothing has been deleted");
  await expect(page.getByTestId("chat-locked-upgrade")).toHaveAttribute("href", "/pricing");

  // There is nothing to type into and nothing to send — the refusal is the whole composer.
  await expect(page.getByTestId("chat-input")).toHaveCount(0);
  await expect(page.getByTestId("chat-send")).toHaveCount(0);

  // And the header says why, with Save offered as what it is: unavailable.
  await expect(page.getByTestId("canvas-locked")).toBeVisible();
  await expect(page.getByTestId("save-agent")).toBeDisabled();
});

test("Share explains the lock instead of failing to mint a link", async ({ page }) => {
  // The refusal a user actually met in production: the popover minted, got a 402, and said
  // "Couldn't create a link. Try again." — advice that could never work. The lock is checked
  // before the request now, and the panel says the same thing the chat and the dashboard do.
  await openProject(page, true);
  await page.getByTestId("share-agent").click();

  const locked = page.getByTestId("share-locked");
  await expect(locked).toBeVisible();
  await expect(locked).toContainText("read-only");
  await expect(page.getByTestId("share-locked-upgrade")).toHaveAttribute("href", "/pricing");
  // Nothing was minted, so there is no link to copy and no "try again".
  await expect(page.getByTestId("share-error")).toHaveCount(0);
  await expect(page.getByTestId("share-url")).toHaveCount(0);
});

test("an unlocked project keeps its composer", async ({ page }) => {
  await openProject(page, false);

  await expect(page.getByTestId("chat-input")).toBeVisible();
  await expect(page.getByTestId("chat-locked")).toHaveCount(0);
  await expect(page.getByTestId("canvas-locked")).toHaveCount(0);
  await expect(page.getByTestId("save-agent")).toBeEnabled();
  await expect(page.getByTestId("share-agent")).toBeEnabled();
});

test("the assistant is read-only too, and says so the same way", async ({ page }) => {
  // The assistant is as expensive as a run and produces something the project cannot keep:
  // drafting burns credits on an LLM call, and Apply then writes to an agent the API refuses.
  // Gating the run but not this left the more galling half open.
  await openProject(page, true, "assistant");

  const locked = page.getByTestId("assistant-locked");
  await expect(locked).toBeVisible();
  await expect(locked).toContainText("Nothing has been deleted");
  await expect(page.getByTestId("assistant-locked-upgrade")).toHaveAttribute("href", "/pricing");

  // The composer is replaced, not disabled — there is nothing to type into and nothing to send.
  await expect(page.getByTestId("assistant-input")).toHaveCount(0);
  await expect(page.getByTestId("assistant-send")).toHaveCount(0);
  // And no example openers: `onPick` is `send`, so one click would fire a draft the API
  // refuses, turning an invitation into an error bubble.
  await expect(page.getByTestId("assistant-example")).toHaveCount(0);
});

test("an unlocked project keeps the assistant composer", async ({ page }) => {
  await openProject(page, false, "assistant");

  await expect(page.getByTestId("assistant-input")).toBeVisible();
  await expect(page.getByTestId("assistant-locked")).toHaveCount(0);
  await expect(page.getByTestId("assistant-example").first()).toBeVisible();
});
