// Analytics stub. PostHog is wired in a later MVP week (see MVP-EXECUTION-PLAN.md); until
// then `track` is a no-op so the call sites exist and can be lit up in one place.
export type AnalyticsEvent =
  | "assistant_prompted"
  | "assistant_graph_applied"
  | "assistant_restore"
  | "assistant_error";

export function track(event: AnalyticsEvent, props?: Record<string, unknown>): void {
  // no-op until PostHog is configured; kept as a typed seam so call sites already exist.
  void event;
  void props;
}
