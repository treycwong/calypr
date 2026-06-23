import { betterAuth } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { Pool } from "pg";

/**
 * The Better Auth server instance — used only when Better Auth is configured
 * (`BETTER_AUTH_SECRET` + `DATABASE_URL` + GitHub OAuth creds). `secret` and `baseURL` are
 * read from `BETTER_AUTH_SECRET` / `BETTER_AUTH_URL` by default. The `pg` Pool is lazy, so
 * importing this module is safe even with no database reachable (the dev-auth path never does).
 */
export const auth = betterAuth({
  database: new Pool({ connectionString: process.env.DATABASE_URL }),
  socialProviders: {
    github: {
      clientId: process.env.GITHUB_CLIENT_ID ?? "",
      clientSecret: process.env.GITHUB_CLIENT_SECRET ?? "",
    },
  },
  // nextCookies() must be last — lets Better Auth set cookies through Next server actions.
  plugins: [nextCookies()],
});
