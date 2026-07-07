"use client";

import { useEffect } from "react";

import { initAnalytics } from "@/lib/analytics";

// Mounts once in the root layout to start PostHog (pageviews + autocapture). Renders
// nothing; a no-op when NEXT_PUBLIC_POSTHOG_KEY is unset (dev/CI).
export function AnalyticsInit() {
  useEffect(() => {
    initAnalytics();
  }, []);
  return null;
}
