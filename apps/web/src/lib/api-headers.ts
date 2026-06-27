import { getSession } from "@/lib/auth";

// Headers that identify a proxied request to the Python API: the shared internal key proves the
// Next proxy is the trusted caller, and the user id selects that user's workspace. Server-side
// only (reads the session + the secret env). When CALYPR_INTERNAL_KEY is unset (local/CI) the
// API falls back to the shared dev workspace, so this is a no-op there.
export async function internalHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {};
  const key = process.env.CALYPR_INTERNAL_KEY;
  if (!key) return headers;
  headers["x-calypr-internal-key"] = key;
  const session = await getSession();
  if (session?.userId) headers["x-calypr-user-id"] = session.userId;
  return headers;
}
