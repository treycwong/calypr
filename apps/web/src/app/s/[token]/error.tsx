"use client";

import { ErrorFallback } from "@/components/ErrorFallback";

export default function ShareError({ reset }: { error: Error; reset: () => void }) {
  return (
    <ErrorFallback
      title="This shared agent couldn't load"
      description="Something went wrong. Try again, or ask for a fresh link."
      reset={reset}
    />
  );
}
