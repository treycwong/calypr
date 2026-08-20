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
    google: {
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    },
  },
  // There is deliberately **no `account.accountLinking` block**, and adding one would be a
  // mistake. Better Auth's defaults are already the secure behaviour we want: linking is on,
  // implicit linking is on, and `requireLocalEmailVerified` is on — so a second provider folds
  // into an existing `user` row only when the local row's email is provider-verified.
  //
  // That default is load-bearing here. `billing_account.owner_user_id` *is* this `user.id`
  // (see migration 0016 / `resolve_account()`), so a duplicate user row means a duplicate
  // billing account — a second plan, a second credit balance, and the person's own agents
  // invisible to them. Both providers report verification honestly (GitHub from /user/emails,
  // Google from the `email_verified` claim), so the gate holds.
  //
  // In particular, do not add `trustedProviders` to "fix" a refused link. A refusal means the
  // existing row's email was never verified, and trusting the provider past that is exactly the
  // pre-registration takeover the gate exists to stop — which, given the beta-invite matching on
  // `x-calypr-user-email` below, would hand out a paid feature.
  session: {
    // Better Auth gates its "sensitive" operations on session *freshness*, and `deleteUser` is
    // one of them: without this it throws `SESSION_EXPIRED` unless the session was created
    // within `freshAge` (default 24h) **or** the request carries a password. Our users sign in
    // with GitHub, so they have no `credential` account and the password branch is unreachable —
    // meaning anyone who signed in more than a day ago could never complete a deletion.
    //
    // Setting it to 0 buys back nothing an attacker didn't already have: a stolen session can
    // call our own `DELETE /api/account`, which is the request that actually destroys the data
    // and has no freshness check of its own. The friction that matters is the typed
    // confirmation in the dialog, not this.
    freshAge: 0,
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
