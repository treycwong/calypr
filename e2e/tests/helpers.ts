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
 * Nothing already in the DOM distinguishes "rendered" from "interactive": `.react-flow__controls`
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
  await expect(page.locator(".react-flow__controls")).toBeVisible();
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
