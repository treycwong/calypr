import { dash } from "@better-auth/infra";
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
  user: {
    // Opt-in, required for `authClient.deleteUser()`. It removes the Better Auth identity —
    // the `user`/`session`/`account` rows — and clears the session cookie, which is the one
    // thing our own `DELETE /api/account` deliberately cannot do (see that route).
    //
    // This exposes `POST /api/auth/delete-user` to any signed-in session with no confirmation
    // email. Acceptable here: all of our data sits behind `/api/account`, so the worst this
    // alone achieves is signing someone out of an identity they already control. Note the
    // static-segment trap — `/api/auth/signout` and `/api/auth/dev` are *our* routes and shadow
    // the catch-all, so never add a static route at `/api/auth/delete-user`.
    deleteUser: { enabled: true },
    // `changeEmail` stays **off**. The API trusts `x-calypr-user-email` as the provider-verified
    // address and matches it against the beta invite list, so a user who could change their own
    // email could type an invited one and self-grant beta — which includes code export, a paid
    // feature. Enabling this means moving entitlements off the mutable address first.
  },
  // dash() connects this server to the Better Auth hosted dashboard; it reads its key from
  // BETTER_AUTH_API_KEY (set in the deployed env). nextCookies() must stay last — it lets Better
  // Auth set cookies through Next server actions.
  plugins: [dash(), nextCookies()],
});
