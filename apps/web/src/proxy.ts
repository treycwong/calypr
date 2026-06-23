import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/constants";

// Next.js 16 "proxy" (formerly middleware). Protects the app routes: with Clerk when it's
// configured, otherwise via the dev session cookie — so the app runs (and CI/E2E stay
// green) with no keys.
const clerkEnabled = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
const isProtected = createRouteMatcher(["/dashboard(.*)", "/canvas(.*)"]);

function devProxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) {
    return NextResponse.next();
  }
  const signInUrl = new URL("/sign-in", request.url);
  signInUrl.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(signInUrl);
}

export const proxy = clerkEnabled
  ? clerkMiddleware(async (auth, request) => {
      if (isProtected(request)) await auth.protect();
    })
  : devProxy;

export const config = {
  matcher: ["/dashboard/:path*", "/canvas/:path*"],
};
