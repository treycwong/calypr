"use client";

import { ErrorFallback } from "@/components/ErrorFallback";

export default function CanvasError({ reset }: { error: Error; reset: () => void }) {
  return (
    <ErrorFallback
      title="Something broke on the canvas"
      description="The editor hit an unexpected error. Your saved agents are safe."
      reset={reset}
    />
  );
}
