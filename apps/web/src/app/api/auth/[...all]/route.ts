import { toNextJsHandler } from "better-auth/next-js";

import { auth } from "@/lib/auth-server";

// Better Auth's catch-all endpoint (sign-in, OAuth callback, session, sign-out). Only
// exercised when Better Auth is configured; the dev-auth path never calls it.
export const { POST, GET } = toNextJsHandler(auth);
