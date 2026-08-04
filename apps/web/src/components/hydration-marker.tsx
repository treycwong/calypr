"use client";

import { useEffect } from "react";

/**
 * Marks `<html data-hydrated="true">` once React has attached on the client.
 *
 * **Why the app carries this rather than the tests.** Almost every page here is a `"use client"`
 * component, which still server-renders — so buttons arrive in the HTML complete with their
 * `data-testid`, visible and clickable, some time before `onClick` exists. A click in that gap is
 * silently dropped: no error, no navigation, nothing. In Playwright it surfaces as the *next*
 * assertion failing ("node-input not found"), which reads like a broken feature rather than a
 * timing problem, and it moves to a different test on every run depending on machine load.
 *
 * Everything a test could wait for instead is a lie in this specific way. `.react-flow__controls`
 * being visible says the markup rendered. `toBeEnabled()` reads an attribute the server wrote.
 * Both are true well before the handler is live.
 *
 * The alternative was retrying every click until it took effect, at ~50 call sites across 14
 * spec files — treating the symptom, in fifty places, forever. One attribute the app sets when
 * the statement "React is attached" becomes true is the smaller and more honest thing.
 *
 * Costs nothing at runtime: one effect, once, no render, no state.
 */
export function HydrationMarker() {
  useEffect(() => {
    document.documentElement.dataset.hydrated = "true";
  }, []);
  return null;
}
