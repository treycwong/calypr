// Feature gates for work that has landed but isn't ready to be switched on for everyone.

/**
 * Build-time switch: `NEXT_PUBLIC_ROUNDTRIP_ENABLED=1`. Must be referenced statically for the
 * bundler to inline it. Production deliberately leaves this unset.
 */
const BUILD_FLAG = process.env.NEXT_PUBLIC_ROUNDTRIP_ENABLED === "1";

/** Per-browser opt-in, so the feature can be exercised without a rebuild. */
export const ROUNDTRIP_OPT_IN_KEY = "calypr:roundtrip";

/**
 * Reverse round-trip UI: editable code + "Apply to canvas".
 *
 * The parser behind it (Weeks 5–7) is merged and proven, but the loop stays invisible in
 * production until it's switched on. Two ways in, neither of which is on by default:
 * the build flag above, or `localStorage["calypr:roundtrip"] = "1"` in a given browser.
 *
 * The localStorage route is what the e2e suite uses, so enabling the feature for one spec
 * doesn't change the Code tab (a `<pre>` vs a `<textarea>`) for every other spec. It also
 * lets us dogfood on a deployed build without shipping it to users.
 *
 * **Client-only** — reads `localStorage`, so call it from an effect, never during render, or
 * the server and client markup disagree.
 */
export function roundtripEnabled(): boolean {
  if (BUILD_FLAG) return true;
  try {
    return localStorage.getItem(ROUNDTRIP_OPT_IN_KEY) === "1";
  } catch {
    return false; // storage blocked (private mode, embedded context) → stay off
  }
}
