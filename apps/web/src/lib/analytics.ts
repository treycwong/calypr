// PostHog analytics (MVP-EXECUTION-PLAN Week 1). Env-gated: without NEXT_PUBLIC_POSTHOG_KEY
// every call is a no-op, so dev/CI/e2e stay network-free. The `code_*` events are THE ceiling
// events — the thesis metric ("leave with the code you own") the Month gates read.
import posthog from "posthog-js";

export type AnalyticsEvent =
  // ceiling events (CodeView)
  | "code_view_opened"
  | "code_copied"
  | "code_downloaded"
  // ceiling-RESOLUTION events (reverse round-trip): the user didn't just leave with the code,
  // they edited it and came back. `parse_degraded` is the honest one — it counts the times we
  // couldn't fully understand an edit and fell back to a Custom Code node.
  | "code_edited"
  | "parse_applied"
  | "parse_failed"
  | "parse_degraded"
  // playground runs
  | "run_started"
  | "run_completed"
  | "run_errored"
  // starters
  | "template_selected"
  // AI assistant
  | "assistant_prompted"
  | "assistant_graph_applied"
  | "assistant_restore"
  | "assistant_error";

let initialized = false;

/** Initialize PostHog once, client-side. Safe to call repeatedly; no-op without a key. */
export function initAnalytics(): boolean {
  if (initialized) return true;
  if (typeof window === "undefined") return false;
  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  if (!key) return false;
  posthog.init(key, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com",
    // SPA-aware pageviews: capture on history pushState/replaceState/popstate too.
    capture_pageview: "history_change",
  });
  initialized = true;
  return true;
}

export function track(event: AnalyticsEvent, props?: Record<string, unknown>): void {
  if (initAnalytics()) posthog.capture(event, props);
}
