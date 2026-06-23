import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/constants";

// Dev-only sign-in: set the session cookie and bounce to `next` (default /dashboard).
// Bypassed when Better Auth is configured (BETTER_AUTH_SECRET) — its /api/auth/[...all]
// handler owns sign-in then.
export async function POST(request: Request) {
  const url = new URL(request.url);
  const next = url.searchParams.get("next") || "/dashboard";
  const res = NextResponse.redirect(new URL(next, url.origin), { status: 303 });
  res.cookies.set(SESSION_COOKIE, "dev-user", {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 7,
  });
  return res;
}
