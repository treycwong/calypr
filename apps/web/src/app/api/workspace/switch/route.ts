// Set (or clear) which workspace the user has open.
//
// Deliberately does no validation. The cookie is a UI preference, and the API checks it against
// the caller's account on the very next request — `GET /workspaces/current` returns the workspace
// it actually resolved, so a stale or foreign value self-corrects on the next paint rather than
// erroring here. Validating in two places would mean two places to disagree.
//
// An empty/absent `workspace_id` clears the cookie, which is what sign-out uses: without that, the
// next person to sign in on a shared machine would send someone else's id. Harmless — the API
// rejects it — but it would land them on a confusing "wrong workspace" first paint.
import { cookies } from "next/headers";

import { WORKSPACE_COOKIE } from "@/lib/constants";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  let workspaceId = "";
  try {
    const body = (await req.json()) as { workspace_id?: unknown };
    if (typeof body.workspace_id === "string") workspaceId = body.workspace_id;
  } catch {
    // An empty or unparseable body means "clear it".
  }

  const store = await cookies();
  if (workspaceId) {
    store.set(WORKSPACE_COOKIE, workspaceId, {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure: process.env.NODE_ENV === "production",
      maxAge: 60 * 60 * 24 * 365,
    });
  } else {
    store.delete(WORKSPACE_COOKIE);
  }
  return new Response(null, { status: 204 });
}
