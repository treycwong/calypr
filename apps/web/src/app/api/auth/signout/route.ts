import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/constants";

export async function POST(request: Request) {
  const url = new URL(request.url);
  const res = NextResponse.redirect(new URL("/sign-in", url.origin), { status: 303 });
  res.cookies.delete(SESSION_COOKIE);
  return res;
}
