/** Cookie the dashboard sidebar's collapsed state lives in (`"1"` = collapsed). Read by
 *  `app/dashboard/layout.tsx` on the server so the rail renders at the right width on first paint,
 *  and written by the sidebar's toggle. Lives outside the client component because a server
 *  component importing a plain value from a `"use client"` module gets a client reference, not
 *  the string. */
export const SIDEBAR_COOKIE = "calypr-sidebar";
