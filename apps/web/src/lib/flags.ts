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
 * Reverse round-trip UI: editable code + "Apply to canvas".
 *
 * The parser behind it (Weeks 5–7) is merged and proven; the loop is open to a **beta cohort**
 * rather than everyone while it settles in the wild. Three ways in, none on by default:
 *
 * 1. the workspace's `plan` (`beta`/`plus`) — the real, server-owned gate;
 * 2. the build flag above (a whole deployment);
 * 3. `localStorage["calypr:roundtrip"] = "1"` in a single browser.
 *
 * (2) and (3) are developer overrides, not entitlement. (3) in particular is what the e2e suite
 * uses: enabling the feature for one spec must not turn the Code tab from a `<pre>` into a
 * `<textarea>` for the five other specs that assert on `code-output`.
 *
 * This is a **product-surface gate, not a security boundary** — `POST /parse` is public and
 * costs nothing to serve (a pure function, no model call), and the parser itself ships as OSS.
 * Someone who flips their own localStorage gets an unfinished UI, not privileged access.
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
