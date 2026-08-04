# Calypr — Settings → Account Plan (profile, GitHub, Delete Account)

**Date:** 2026-08-02 · **Status:** PLAN for implementation · **Follows:** PR #59
(`8f429b7`, multi-workspace + `billing_account`). Next migration is **0017**.

> Written to be read cold. Every path and line reference below was verified on 2026-08-02
> against `main` at `8f429b7`. Re-check line numbers before trusting them; paths and behaviour
> are the load-bearing part.

---

## 1. What this is

Settings → Account is read-only today: it renders name / email / avatar from props plus a plan
badge, and says *"Your account details come from your sign-in provider (GitHub)."* Replace it
with three Railway-style cards:

1. **Account Information** — editable name + avatar URL, email shown read-only.
2. **Account Integrations** — GitHub, connected state only.
3. **Danger** — Delete Account, behind a typed confirmation.

**Scope note:** "Delete Account" means the whole account — every workspace, every project, the
Stripe subscription, the login. It is not "delete project" (that exists on the project card) or
"delete workspace" (shipped in #59).

---

## 2. Two findings that shape the design

### 2a. Email cannot be an editable field

`x-calypr-user-email` is documented in `apps/web/src/lib/api-headers.ts` as *the verified email
from the auth provider*, and the API trusts it:

- `entitlements.grant_beta_if_invited(session, account, email)` matches it against `waitlist`;
- `routers/billing.py::create_checkout` seeds the Stripe customer from it.

So a free-text email field lets any user type an invited address and self-grant **beta — which
includes code export, a paid feature**. Production had **0 unredeemed invites** on 2026-08-02, so
this is latent rather than live, but the invite list gets reused.

**Decision: email is read-only.** Rendered as text, not a disabled input. Name and avatar stay
editable. If email editing is ever wanted, entitlements must move off it first (match the
provider-verified address, not the mutable one), and it still won't be verified without a
transactional mail provider, which the project does not have.

### 2b. Delete crosses five stores with no transaction

Stripe · Vercel Blob · LangGraph's checkpoint tables · our Alembic tables · Better Auth's tables.

- **There is no Stripe cancellation code anywhere.** Grep `stripe.` in `apps/api` — only
  `checkout.Session.create`, `billing_portal.Session.create`, `Subscription.retrieve`,
  `Webhook.construct_event`. Delete an account today and the card keeps being charged.
- **`calypr_storage` has no delete function.** `services/storage/src/calypr_storage/__init__.py`
  exports only `BlobError, put_blob`. Every uploaded object orphans permanently, and deleting the
  `upload` rows destroys the last pointer to them.
- **`resolve_account` resurrects.** `migrations/versions/0016_accounts_and_workspaces.py:232` is
  find-or-create, called from `deps.py` on **every** request and committed immediately. A DB-only
  delete is silently undone by the next page load.

**Decisions:** soft-delete + background purge; Stripe cancelled synchronously at request time;
write `delete_blob` and call it best-effort. Grace window **7 days**
(`CALYPR_PURGE_GRACE_DAYS`, Railway env).

---

## 3. Facts a cold session needs

**Auth.** `apps/web/src/lib/auth.ts` — `Session = {userId,name,email,image}`,
`betterAuthEnabled()` = `!!process.env.BETTER_AUTH_SECRET`, `getSession()`. In the **dev path**
`getSession()` returns hardcoded `{userId: <cookie>, name:"Developer", email:"dev@calypr.local",
image:null}` — **there is no profile store**, and `app/api/auth/dev/route.ts` always sets the
cookie to the literal `"dev-user"`. **CI and the whole e2e suite run in dev mode.**

Better Auth is **1.6.20**. Client methods: `updateUser`, `changeEmail`, `deleteUser`,
`listUserAccounts`. `deleteUser` requires opt-in config. The client returns `{data, error}` and
**does not throw**.

> **Static-segment trap:** `/api/auth/signout` and `/api/auth/dev` are *our* routes and shadow the
> Better Auth catch-all at `app/api/auth/[...all]/route.ts`. Better Auth's own is
> `/api/auth/sign-out` (hyphenated). **Do not add a static route at `/api/auth/delete-user`.**

**Table naming ban.** Better Auth owns `user`, `session`, `account`, `verification` in the *same*
Neon database, outside Alembic — invisible to `alembic upgrade` and absent from any local DB that
has never run the web app's auth. This already cost a deploy in #59 (a table named `account`
collided; it became `billing_account`). Neon also keeps a **second copy in a `neon_auth` schema**,
so schema-qualify anything reading `information_schema`.

**Tenant model (0016).** `billing_account` (owner_user_id = Better Auth user.id, UNIQUE nullable;
plan; stripe_customer_id; stripe_subscription_id; credit_balance_micro; grant_cycle_anchor;
storage_bytes; storage_measured_at) ← `workspace.account_id` FK CASCADE.

**Cascade from `billing_account` DELETE:** `workspace`, `credit_ledger` direct; `agent`, `run`,
`run_usage`, `connector_credential`, `provider_key`, `share_link`, `upload` via workspace.
**NOT cascaded:** LangGraph `checkpoints`/`checkpoint_blobs`/`checkpoint_writes`, Vercel Blob
objects, Better Auth rows, `stripe_event`, `waitlist` (keyed by email).

**Threads.** `apps/api/src/calypr_api/threads.py` namespaces authenticated threads
`ws:<workspace_id>:<suffix>` and exposes `workspace_prefix(workspace_id)`. Share threads are
`share:<token>:<suffix>`. `storage_usage.py` already has the union query (prefix match UNION join
through `run.thread_id`) and a children-first deleter `_delete_threads(session, thread_ids)`.

**Dev carve-out.** `if not settings.internal_key: return uuid.UUID(DEV_WORKSPACE_ID)` is the first
statement in every resolver in `deps.py` and touches no DB. `start.sh` promises the app runs with
no Postgres. **Preserve this exactly** — every phase below depends on it.

**Settings UI idiom.** `apps/web/src/components/dashboard/settings-view.tsx`. Canonical editable
field = the workspace rename block: card `rounded-lg border border-border p-5`, `<label htmlFor>`
+ `text-sm font-medium`, `mt-0.5 text-xs text-muted-foreground` description, row
`mt-2 flex items-center gap-2`, `<Input className="max-w-xs">`, `<Button size="sm">`, inline
`<span className="text-xs text-muted-foreground">` with literal "Saving…" / "Saved ✓" /
"Save failed". **settings-view.tsx uses no toasts** — don't introduce them here.
`name`/`email`/`image` arrive as **props** from `app/dashboard/settings/page.tsx`.
UI kit is **base-ui**, not Radix: `<DialogClose render={<Button/>} />`, **not** `asChild`.
Destructive-confirm precedent: `app/dashboard/page.tsx` ("Delete project?", one click, no error
handling — copy the structure, not the missing error handling).

---

## 4. Phases

### Phase 1 — `delete_blob`

`services/storage/src/calypr_storage/blob.py` already inline-strips the token inside `put_blob`
(whitespace + stray quotes; a pasted `.env` snippet 403s opaquely). Extract as `_auth(token)` so
the two cannot drift, then add:

```python
async def delete_blob(urls: str | Iterable[str], *, token=None, timeout=30.0) -> None:
    """POST {_BASE_URL}/delete  {"urls": [...]}  — same bearer + x-api-version as put_blob."""
```

Idempotent on Vercel's side (deleting an already-gone url is a 200), so callers may retry. Empty
input is a no-op, not an error. Chunk at 100 urls. Raises `BlobError` like `put_blob` —
deliberately **no partial-success return value**: "which ones made it" is a policy question and
the answer belongs to the purge job. Export from `__init__.py`.

### Phase 2 — Migration `0017_account_deletion`

- `billing_account.deleted_at timestamptz NULL` + partial index `WHERE deleted_at IS NOT NULL`.
  Only that column — purge state lives in `account_purge`, so there is one source of truth for
  "is this finished".
- **`account_purge`** (name follows the `billing_account` precedent; see the naming ban):
  `id`, `account_id` UNIQUE **with no FK** (the purge's last step deletes that row and this record
  must outlive it as the audit trail — a dangling id is the point), `owner_user_id`,
  `thread_prefixes[]`, `legacy_thread_ids[]`, `blob_urls[]`, `blob_urls_failed[]`,
  `stripe_customer_id`, `stripe_subscription_id`, `stripe_cancelled_at`, `requested_at`,
  `started_at`, `purged_at`, `attempts`, `last_error`. Partial index on `requested_at WHERE
  purged_at IS NULL`. No RLS — never read through a tenant session, same as the GC paths.
  **No email column**: storing the email of an account someone asked us to delete defeats the
  request.

**Why a durable record instead of collect-and-purge inline.** The purge crosses a
non-transactional store and both orderings lose without it: blobs-first then crash leaves `upload`
rows pointing at nothing; DB-first then crash loses the urls forever and those objects are then
unreachable *and still billing*. Storing **prefixes** rather than expanded thread ids keeps the
row small regardless of conversation count.

Replace **`resolve_account` only** — `resolve_workspace(text,uuid)` and `list_account_workspaces`
call it by name and resolve at call time.

### Phase 3 — Make soft-delete stick (**build and test before Phase 4**)

The guard must be *inside* the upsert. A `SELECT … IF deleted THEN RAISE` in front of the INSERT
loses the race against a concurrent soft-delete; a predicate on `DO UPDATE` does not, because the
upsert takes the row lock before evaluating it.

```sql
INSERT INTO billing_account (owner_user_id) VALUES (p_user_id)
ON CONFLICT (owner_user_id) DO UPDATE SET owner_user_id = EXCLUDED.owner_user_id
    WHERE billing_account.deleted_at IS NULL
RETURNING id INTO acc;

IF acc IS NULL THEN
    -- Raise, don't return NULL: every caller reads a uuid as "proceed", so a caller that
    -- forgot to null-check would fail *open*. An exception cannot be forgotten.
    RAISE EXCEPTION 'account % is deleted', p_user_id USING ERRCODE = 'CY001';
END IF;
```

`deps.py` gains `is_account_deleted(exc)` matching **SQLSTATE `CY001`** (psycopg3: `exc.orig.sqlstate`),
never the message. Four call sites return **401**:

1. `_resolve_workspace_id` — covers `tenant`, `request_workspace`, `require_code_export`. Must
   `session.rollback()` first; the RAISE aborted the transaction.
2. **`run_workspace`** — check *before* its blanket `except Exception: return dev`, or a deleted
   account keeps streaming runs metered against the shared dev account.
3. `routers/workspaces.py::list_workspaces` — `list_account_workspaces` calls `resolve_account`,
   so `GET /workspaces` would 500.

401 rather than 403: the account genuinely no longer exists, and it matches what these already
return for a bad key, so the web layer needs no new branch.

### Phase 4 — The delete request

`billing.cancel_subscription(account) -> bool` — **immediate** `stripe.Subscription.cancel`, not
`cancel_at_period_end`: an account that no longer exists must not carry a live subscription for
another three weeks. Promote `_is_missing_customer` from `routers/billing.py` into `billing.py`
so both callers share it (check its two existing call sites still work); a subscription Stripe
says is already gone counts as success.

New `routers/account.py`, `DELETE /account`, `Depends(tenant)`, in this order:

0. **Dev carve-out first** — no internal key, or the dev workspace → **501**. The dev account is
   seeded by 0016; marking it deleted breaks every CI run permanently. The step-3 `UPDATE` also
   carries `AND owner_user_id IS NOT NULL` as belt and braces.
1. Already `deleted_at` → 200, no-op (idempotent).
2. **Stripe cancel. On failure → 502, change nothing.** Deleting an account whose subscription
   keeps charging is the one failure we cannot let through. No row has been touched, so retry is
   free; the dialog shows the message inline.
3. **Collect, record and mark — one transaction.** Workspace ids → `ws:<id>:`; share tokens →
   `share:<token>:`; `run.thread_id` values matching *neither* prefix (pre-`threads.py`, reachable
   only through `run`); `upload.blob_url` joined through `workspace.account_id` — **that join is
   the only guarantee we never point a permanent delete at an object the account doesn't own.**
   Insert `account_purge`, set `deleted_at`, reset the plan/subscription mirror, and
   `DELETE FROM waitlist WHERE lower(email) = lower(:email)`.

Nothing cascades in the request.

Web proxy `app/api/account/route.ts` clears `SESSION_COOKIE` + `WORKSPACE_COOKIE` and translates
the dev **501 → `{deleted: true, mode: "dev"}`**. It does **not** clear Better Auth's cookie — the
name is environment-dependent (`__Secure-` prefixed in prod) and guessing it ships a delete that
leaves people logged in. `authClient.deleteUser()` clears it.

### Phase 5 — The purge job

Promote `storage_usage._delete_threads` → public `delete_threads` (keep the private alias); the
children-first ordering knowledge should live in one place.

New `purge.py`, exposed as `POST /internal/gc/purge-accounts` behind the existing
`_require_internal_key` in `routers/internal.py` (fails closed at 503 — correct for a delete
endpoint), and added to the **existing** loop in `apps/web/src/app/api/cron/gc/route.ts`:
`["purge-accounts", "checkpoints", "measure-storage"]`. **No new `vercel.json` cron** — Vercel
Hobby allows two and one is already used. Purge first so `measure-storage` doesn't scan accounts
about to vanish.

Per account, claimed with `FOR UPDATE SKIP LOCKED`, `attempts` incremented and **committed
immediately** so a record that reliably kills the process doesn't retry forever
(`attempts >= 5` is left with its `last_error` for a human):

1. **Blobs**, chunks of 100, draining `blob_urls` as each chunk succeeds. `BlobError` → move the
   chunk to `blob_urls_failed`, warn, continue. **A blob failure never blocks the DB purge.**
2. **Checkpoints — before the cascade, mandatory.** Loop each prefix
   `LIKE :prefix || '%' LIMIT :batch` → `delete_threads` → commit; then the legacy ids chunked.
3. **Cascade** — one `DELETE FROM billing_account`. Hard delete, not a tombstone: `account_purge`
   is the audit trail, and removing the row frees the `owner_user_id` / `stripe_customer_id`
   UNIQUE slots so a returning user gets a clean account rather than a permanent lockout.
4. `purged_at = now()`. Each account in its own try/except.

> **⚠ The ordering constraint that rots silently.** Thread ids must be collected **before** the
> cascade drops `run`/`workspace`. Afterwards the pre-prefix threads are unreachable **and no GC
> arm covers them** — `gc_checkpoints`'s orphan arm excludes `ws:%`, and its TTL arm joins
> run → workspace → billing_account, all of which are gone. Get this wrong and the bytes leak
> forever with zero GC coverage. `test_purge.py`'s headline test exists to catch exactly this.

### Phase 6 — Better Auth + web glue

`apps/web/src/lib/auth-server.ts`: add `user: { deleteUser: { enabled: true } }`. Leave
`changeEmail` **off** (§2a). `nextCookies()` stays last in `plugins`.

> This exposes `POST /api/auth/delete-user` to any signed-in session with no verification email.
> Acceptable — our data sits behind `/api/account` — but see the static-segment trap in §3.

**Client order — our API first, Better Auth second:** `DELETE /api/account` → on 200
`authClient.deleteUser()` → redirect to `/sign-in?deleted=1`. If step 2 fails the account is
already soft-deleted and every call 401s, so retry is safe. The reverse order destroys the
identity we need to *find* the account, orphaning a live subscription nobody can cancel. If step 2
errors, still `signOut()` and redirect — never leave someone signed into an account that no longer
functions.

### Phase 7 — UI

`SettingsView` gains `manageable: boolean` and `providers: string[]`, both resolved server-side in
`app/dashboard/settings/page.tsx` (it already passes name/email/image as props;
`auth.api.listUserAccounts` there avoids a client round-trip and a loading flash).
**Preserve `account-plan` and `account-upgrade`** — `e2e/tests/phase-settings.spec.ts` asserts them.

1. **Account Information** (`account-info-card`) — avatar previews **local** state so a URL edit
   updates live; `account-name` + `account-image` + one `account-save` (a single `updateUser`
   call) + `account-saved`. Separator, then email as **text, not a disabled input** — read-only
   means no field: *"Your email comes from GitHub and can't be changed here."*
2. **Account Integrations** (`account-integrations-card`) — GitHub row, `Badge` connected /
   not connected, `data-connected` attribute. **Connected state only, no disconnect**: GitHub is
   the only provider, so unlinking locks the user out of their own account.
3. **Danger** (`account-danger-card`, `border-destructive/40`) — copy names exactly what goes:
   workspaces, projects, run history, uploads, credit balance; **subscription cancelled
   immediately, no refund for the remainder of the period**; beta invite forfeited; can't be
   undone.

**Type-to-confirm ("delete my account") — a deliberate departure** from the one-click precedent in
`app/dashboard/page.tsx`. That precedent guards one rebuildable graph; this destroys every
workspace, cancels a paid subscription and ends a session the user cannot get back. Copying an
affordance designed for the cheap case into the expensive one is the mistake, not the departure.
Compare `.trim().toLowerCase()`. **Add the error handling the precedent omits** — keep the dialog
open and render the server's message (the Stripe 502 especially) inline; a toast is wrong when the
dialog is modal.

**Dev mode** (CI runs entirely here; there is no profile store): name/avatar rendered **disabled**
with a visible notice, rather than appearing to save and silently reverting on reload. Delete stays
**fully interactive** so the flow is e2e-testable — it 501s, the proxy translates to success,
cookies clear. In dev, "delete account" *is* sign-out, which is honest because there is nothing to
delete; say so in a gated note.

---

## 5. Verification

**Migration** — `alembic upgrade head` → `downgrade -1` → `upgrade head` against the local DB
(which now carries the Better Auth tables — keep it that way). Confirm Better Auth's `account` is
untouched.

**pytest**

- **`test_account_resurrection.py`** — *the property the whole design exists for.* After
  soft-delete: `resolve_workspace` raises **SQLSTATE `CY001`** (assert the code, never the
  message); **no new workspace row** is created; and `tenant` / `request_workspace` /
  `run_workspace` / `GET /workspaces` each 401 — four separate asserts. `run_workspace`'s blanket
  `except` is precisely the regression this guards. **After purge**, resolution succeeds again and
  returns a *new* workspace id.
- **`test_account_delete.py`** — the request writes one `account_purge` row and **cascades
  nothing**; collection correctness (prefixes per workspace + share link, legacy ids excluded when
  prefixed, blob urls exactly the account's); **a generic `StripeError` → 502 with `deleted_at`
  still NULL and zero purge rows** (the test that stops a half-delete); `resource_missing`
  succeeds; a second DELETE is a no-op; dev carve-out 501s; the caller's waitlist row is gone.
- **`test_purge.py`** — **headline:** an account with a `ws:` thread, a legacy thread reachable
  *only* via `run.thread_id`, and a `share:` thread ends with zero rows in all three checkpoint
  tables. Fails the moment anyone moves collection after the cascade. Plus: blob failure doesn't
  block the DB purge; idempotent on re-run; **crash-resume** (fail the second chunk, re-run, the
  first chunk's urls are not re-issued) — the test that justifies the durable record; grace window
  respected; a second live account untouched.
- **`services/storage/tests/test_blob.py`** — extend the existing `httpx.MockTransport` harness:
  POSTs to `/delete` with the right body and headers; empty input makes **no** HTTP call; missing
  token raises; >100 urls produce multiple requests; non-200 raises.

**e2e** — `phase14-account.spec.ts`, dev mode: three cards; dev notice; inputs disabled; email
shown with no input; `data-connected="false"`; confirm disabled until the exact phrase;
**Cancel leaves you signed in** (the important negative test); Confirm lands on `/sign-in` and
`/dashboard` bounces back. Re-run `phase-settings.spec.ts`.

> **base-ui menus/dialogs race hydration in Playwright.** The trigger is server-rendered and
> clickable before React attaches, so a click can be swallowed. Use the retry helper added in
> `e2e/tests/phase13-workspaces.spec.ts` (`expect(async () => {...}).toPass()`), don't assume the
> first click landed. Separately, `phase-assistant-model.spec.ts` flakes ~once per full serial run
> for unrelated pre-existing reasons — if it fails, it isn't this work.

**Manual, staging, before shipping** — the two things no test covers: a real Stripe **test-mode**
subscription cancelled by the delete path, and a real throwaway blob deleted by the purge.

---

## 6. Irreversible steps, gaps, ops

1. **The purge cannot be undone.** The 7-day grace window is the only recovery, and it is
   operator-only — the user cannot self-serve, because the sign-in is gone.
2. **Do not downgrade past 0017 in production** after the first deletion — dropping `deleted_at`
   makes every marked-but-unpurged account live again and every purged one a broken shell. Put
   this in the downgrade docstring.
3. **Stripe cancel is immediate and forfeits the paid remainder, unprorated.** Intentional; the
   dialog copy must say so. We do **not** delete the Stripe *customer* — invoices and tax records
   must survive.
4. **Known gap — blobs we cannot delete.** `packages/nodes/src/calypr_nodes/_assets.py` (image-node
   output) records no `upload` row at all, and share-page uploads pass `workspace_id=None`
   (`routers/uploads.py`). Those objects survive account deletion permanently and are
   unattributable — a real gap in a "delete my account" promise, not a nit. Follow-up: record both
   in `upload`. Until then the danger copy says "uploads", not "all your files".
5. **Ops** — `CALYPR_PURGE_GRACE_DAYS` goes on **Railway** (API), not Vercel. Confirm
   `BLOB_READ_WRITE_TOKEN` is present in the API environment: `put_blob` already needs it, but the
   purge is the first path that *deletes* with it.

---

## 7. Order

**1 → 2 → 3 (+ its tests) → 4 → 5 → 6 → 7 → e2e.**

Phase 3 gates everything: the non-resurrection property must be provable **before** any code can
create a deleted account. Ship the button first and "delete" is a no-op that silently comes back
on the next page load.
