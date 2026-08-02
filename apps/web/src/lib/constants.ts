// Shared constants safe to import from any runtime (including proxy.ts, which must not
// pull in next/headers). Keep this module dependency-free.

export const SESSION_COOKIE = "calypr_session";

// Which workspace the user last had open. A *preference*, not an authorization claim: the proxy
// forwards it as `x-calypr-workspace-id` and the API validates it against the caller's account,
// falling back to their default when it doesn't belong to them. So a stale or tampered value is
// harmless — see `resolve_workspace(text, uuid)` in migration 0016.
export const WORKSPACE_COOKIE = "calypr_ws";
