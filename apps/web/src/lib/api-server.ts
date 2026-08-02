import "server-only";

import { internalHeaders } from "@/lib/api-headers";
import type { WorkspaceSummary } from "@/lib/api";

// Server-component reads that hit the Python API directly.
//
// Deliberately not going through the same-origin `/api/*` route handlers the client uses: a
// server component fetching its own routes pays a second HTTP hop and has to reconstruct the
// request's cookies to do it. These call the API with `internalHeaders()`, which is what those
// route handlers do anyway.
//
// Everything here **fails soft**. The dashboard shell renders on every page under /dashboard,
// and `start.sh` promises it still renders with no database — so an unreachable API means an
// empty switcher, not an error page.

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

async function get<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      headers: await internalHeaders(),
    });
    if (!res.ok) return fallback;
    return (await res.json()) as T;
  } catch {
    return fallback;
  }
}

/** Every workspace on the signed-in user's account, for the sidebar switcher. */
export function fetchWorkspaces(): Promise<WorkspaceSummary[]> {
  return get<WorkspaceSummary[]>("/workspaces", []);
}
