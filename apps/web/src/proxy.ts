import { getSessionCookie } from "better-auth/cookies";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/constants";

// Next.js 16 "proxy" (formerly middleware). Protects the app routes. When Better Auth is
// configured it does an optimistic session-cookie check (full validation happens in the
// server components); otherwise it falls back to the dev session cookie — so the app runs,
// and CI/E2E stay green, with no keys or database.
const betterAuthEnabled = !!process.env.BETTER_AUTH_SECRET;

function redirectToSignIn(request: NextRequest) {
  const signInUrl = new URL("/sign-in", request.url);
  signInUrl.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(signInUrl);
}

function betterAuthProxy(request: NextRequest) {
  return getSessionCookie(request)
    ? NextResponse.next()
    : redirectToSignIn(request);
}

function devProxy(request: NextRequest) {
  return request.cookies.has(SESSION_COOKIE)
    ? NextResponse.next()
    : redirectToSignIn(request);
}

export const proxy = betterAuthEnabled ? betterAuthProxy : devProxy;

export const config = {
  matcher: ["/dashboard/:path*", "/canvas/:path*"],
};
