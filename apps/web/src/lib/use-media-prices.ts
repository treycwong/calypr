"use client";

import { useEffect, useState } from "react";

/**
 * Credits per billable unit for the flat-rate media blocks, keyed the way the node reports it
 * (`fal-ai/trellis`, `<endpoint>@<resolution>`).
 *
 * Fetched rather than hardcoded: the number shown in the config panel before a run has to be the
 * number the run is charged, and a copy in `graph.ts` would be correct only until the next time a
 * rate moved — wrong in the direction of quoting a price we don't honour.
 *
 * An empty map is the honest failure. The panel shows no estimate rather than a guess: 3D and
 * Video are the two blocks where a wrong number costs real credits.
 */
export function useMediaPrices(): Record<string, number> {
  const [prices, setPrices] = useState<Record<string, number>>({});
  useEffect(() => {
    let cancelled = false;
    fetch("/api/media-prices", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .then((p) => {
        if (!cancelled) setPrices(p ?? {});
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return prices;
}
