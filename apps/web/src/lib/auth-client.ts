"use client";

import { createAuthClient } from "better-auth/react";

// Browser client for sign-in / sign-out. With no baseURL it targets the same origin, where
// the /api/auth/[...all] handler lives.
export const authClient = createAuthClient();
