"use client";

import { useEffect, useState } from "react";

import { type Connector, listConnectors } from "@/lib/api";

/** The workspace's saved connectors, shared by the Tool node's dropdown (ConfigPanel) and the
 * Tool node's canvas label. Both need the same list to turn a `mcp_connector_ref` into a name —
 * the ref is all the canvas ever stores, since the server resolves it to a URL at run time.
 *
 * The fetch is cached module-wide: a canvas can hold several MCP Tool nodes and each one renders
 * this, but they all want the same list, and it changes only when Settings changes it. */
let cache: Promise<Connector[]> | null = null;

function load(): Promise<Connector[]> {
  if (!cache) cache = listConnectors().catch(() => []);
  return cache;
}

/** Drop the cache so the next read re-fetches — call after saving or deleting a connector. */
export function invalidateConnectors(): void {
  cache = null;
}

export function useConnectors(): Connector[] {
  const [connectors, setConnectors] = useState<Connector[]>([]);
  useEffect(() => {
    let cancelled = false;
    load().then((rows) => {
      if (!cancelled) setConnectors(rows);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return connectors;
}
