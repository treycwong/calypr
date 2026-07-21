"use client";

import { useCallback, useEffect, useState } from "react";

import { listProviderKeys } from "@/lib/api";

/** Which providers this workspace has a BYO key on file for, plus a `refresh` to re-read after
 * saving or removing one. Empty while loading, and on any error — a failed fetch must never
 * *enable* a frontier model the server would refuse.
 *
 * `refresh` bumps a counter the effect depends on rather than fetching itself, so the fetch
 * (and its setState) stays inside the effect where the lint rules want it. */
export function useProviderKeys(): { keyed: Set<string>; refresh: () => void } {
  const [keyed, setKeyed] = useState<Set<string>>(new Set());
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listProviderKeys()
      .then((rows) => {
        if (!cancelled) {
          setKeyed(new Set(rows.filter((r) => r.has_key).map((r) => r.provider)));
        }
      })
      .catch(() => {
        if (!cancelled) setKeyed(new Set());
      });
    return () => {
      cancelled = true;
    };
  }, [reloads]);

  const refresh = useCallback(() => setReloads((n) => n + 1), []);

  return { keyed, refresh };
}
