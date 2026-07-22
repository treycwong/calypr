// Feature gates for work that has landed but isn't ready to be switched on for everyone.

/**
 * Build-time switch: `NEXT_PUBLIC_ROUNDTRIP_ENABLED=1`. Must be referenced statically for the
 * bundler to inline it. Production deliberately leaves this unset.
 */
const BUILD_FLAG = process.env.NEXT_PUBLIC_ROUNDTRIP_ENABLED === "1";

/** Per-browser opt-in, so the feature can be exercised without a rebuild. */
export const ROUNDTRIP_OPT_IN_KEY = "calypr:roundtrip";

/** Plans entitled to the round-trip. Mirrors `entitlements.has_roundtrip` on the API. */
const ROUNDTRIP_PLANS = new Set(["beta", "plus"]);

/**
 * Code export: editable code + "Apply to canvas".
 *
 * A **paid feature** (`plus`), kept for the existing `beta` cohort. It is not a temporary gate on
 * an unfinished thing — the parser behind it (Weeks 5–7) is merged and proven; the product is
 * closed and export is what a paid plan buys. Three ways in, none on by default:
 *
 * 1. the workspace's `plan` (`beta`/`plus`) — the real, server-owned gate;
 * 2. the build flag above (a whole deployment);
 * 3. `localStorage["calypr:roundtrip"] = "1"` in a single browser.
 *
 * (2) and (3) are developer/test overrides, not entitlement. (3) in particular is what the e2e
 * suite uses: enabling the feature for one spec must not turn the Code tab from a `<pre>` into a
 * `<textarea>` for the five other specs that assert on `code-output` — which is why both
 * overrides stay even though neither is part of the product story.
 *
 * Note the **enforcement gap this leaves**: `POST /parse` is public and unauthenticated, so this
 * is a product-surface gate, not a paywall. Flipping your own localStorage gets you the UI. That
 * was acceptable when export was headed for OSS; now that it is the paid differentiator, the
 * endpoint needs plan-checking server-side before Plus goes on sale.
 *
 * **Client-only** — reads `localStorage`, so read it through `useSyncExternalStore` (or an
 * effect), never during render, or the server and client markup disagree.
 */
export function roundtripEnabled(plan?: string): boolean {
  if (plan && ROUNDTRIP_PLANS.has(plan)) return true;
  if (BUILD_FLAG) return true;
  try {
    return localStorage.getItem(ROUNDTRIP_OPT_IN_KEY) === "1";
  } catch {
    return false; // storage blocked (private mode, embedded context) → stay off
  }
}
