"use client";

import { ErrorFallback } from "@/components/ErrorFallback";

export default function DashboardError({ reset }: { error: Error; reset: () => void }) {
  return (
    <ErrorFallback
      title="Couldn't load the dashboard"
      description="Something went wrong loading your projects."
      reset={reset}
    />
  );
}
