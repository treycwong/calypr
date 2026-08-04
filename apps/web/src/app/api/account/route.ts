// Delete the signed-in user's whole account (every workspace, the subscription, the login).
//
// Thin proxy over the API's `DELETE /account`, with two responsibilities of its own: clearing
// our cookies, and translating the dev-mode 501.
import { NextResponse } from "next/server";

import { internalHeaders } from "@/lib/api-headers";
import { SESSION_COOKIE, WORKSPACE_COOKIE } from "@/lib/constants";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function DELETE() {
  const r = await fetch(`${API_URL}/account`, {
    method: "DELETE",
    cache: "no-store",
    headers: await internalHeaders(),
  });

  // Dev/CI has no account to delete — the API refuses with 501 because the dev account is
  // shared by every anonymous request and seeded by migration 0016. Report it as a success so
  // the whole flow (confirm → cookies cleared → redirected to sign-in) stays exercisable by the
  // e2e suite, but say `mode: "dev"` so the UI can be honest that this was really a sign-out.
  const ok = r.ok || r.status === 501;
  if (!ok) {
    // Pass the API's message through untouched — the Stripe 502 in particular is the one the
    // user needs to read, and the dialog renders it inline.
    return new Response(await r.text(), {
      status: r.status,
      headers: { "content-type": "application/json" },
    });
  }

  const res = NextResponse.json(
    r.status === 501 ? { deleted: true, mode: "dev" } : await r.json(),
  );
  res.cookies.delete(SESSION_COOKIE);
  res.cookies.delete(WORKSPACE_COOKIE);
  // Deliberately **not** Better Auth's session cookie. Its name is environment-dependent
  // (`__Secure-`-prefixed over https), so guessing it here ships a delete that silently leaves
  // people signed in. `authClient.deleteUser()` on the client clears it properly.
  return res;
}
