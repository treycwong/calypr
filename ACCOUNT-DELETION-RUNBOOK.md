# Account deletion — production rollout runbook

**For:** PRs #60 (backend) and #61 (web). **Date:** 2026-08-04.

Read this before merging. It is written to be followed top to bottom, in one sitting for steps
0–2, with step 3 either seven days later or forced (see below).

> **The one rule:** never run any of this against your own account. Deletion is irreversible once
> the purge runs, and the sign-in is part of what gets destroyed — there is no self-serve
> recovery, and the operator recovery is only "before the purge". Use a throwaway GitHub account.

## Setup

```bash
export API="https://<your-railway-api-host>"   # same value as CALYPR_API_URL on Vercel
export KEY="<CALYPR_INTERNAL_KEY>"             # same value on Railway and Vercel
```

`psql` below means any Neon SQL console against the **production** database.

---

## Step 0 — before merging anything

- [x] `BLOB_READ_WRITE_TOKEN` present on Railway — **confirmed 2026-08-04.**
- [ ] `CALYPR_PURGE_GRACE_DAYS` — **optional**, defaults to 7 (`config.py`). Set it only to change
      the window.
- [ ] Note the current migration head, so you can tell the deploy actually ran:

```sql
SELECT version_num FROM alembic_version;   -- expect 0016_accounts_and_workspaces
```

---

## Step 1 — merge #60, and let Railway finish

Merge #60 **first** and wait for the Railway deploy to go green before touching #61. The
migration runs as `preDeployCommand` (`railway.json`), so merging *is* migrating.

#60 alone is low risk: no account is deleted yet, so the rewritten `resolve_account` behaves
exactly as before, and the purge job finds nothing. It does expose `DELETE /api/account` with no
UI — reachable by `curl` for a signed-in user against their own account, one merge before the
button exists.

**Verify the migration landed:**

```sql
SELECT version_num FROM alembic_version;                    -- expect 0017_account_deletion
SELECT count(*) FROM account_purge;                         -- expect 0
SELECT column_name FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'billing_account'
   AND column_name = 'deleted_at';                          -- expect one row
```

**Confirm Better Auth's own tables are untouched** — this is the collision that cost a deploy in
#59, and Neon keeps a second copy in a `neon_auth` schema, so schema-qualify:

```sql
SELECT table_schema, table_name FROM information_schema.tables
 WHERE table_name IN ('user','session','account','verification')
 ORDER BY table_schema;
```

**Verify the purge endpoint answers and does nothing:**

```bash
curl -sS -X POST "$API/internal/gc/purge-accounts" -H "x-calypr-internal-key: $KEY"
# expect: {"purged":0,"failed":0,"considered":0}
```

If this 503s, `CALYPR_INTERNAL_KEY` isn't set on Railway — it fails closed on purpose. A 401 means
the key doesn't match the one you exported.

**Sanity-check the nightly job still works end to end** (it now runs purge → checkpoints →
measure-storage):

```bash
curl -sS "https://calypr.co/api/cron/gc" -H "authorization: Bearer $CRON_SECRET"
```

At this point nothing has changed for any user. If something looks wrong, revert the code —
**do not `alembic downgrade`** (see *Rollback* below).

---

## Step 2 — merge #61, then delete a throwaway account

Merge #61. Sign in with a **throwaway GitHub account**.

**2a. Non-destructive first** (Settings → Account):

- Edit the display name → Save → reload. It should persist. *This is the first time
  `authClient.updateUser` runs against a real profile store.*
- Upload an avatar (PNG/JPEG/WebP/GIF, ≤5MB) → the avatar previews immediately → Save → reload.
- Confirm the GitHub row reads **Connected**.

Check the upload was recorded, and keep the URL — you will verify it is really gone in step 3:

```sql
SELECT u.blob_url, u.bytes, u.created_at
  FROM upload u JOIN workspace w ON w.id = u.workspace_id
  JOIN billing_account a ON a.id = w.account_id
 WHERE a.owner_user_id = '<throwaway better-auth user id>'
 ORDER BY u.created_at DESC LIMIT 5;
```

Open the `blob_url` in a browser — it should load. Note it down.

**2b. The negative test.** Open the delete dialog, type the phrase, press **Cancel**. You must
still be signed in and everything must still work.

**2c. Delete.** Open the dialog, type `delete my account`, confirm. Expect: redirect to
`/sign-in?deleted=1` with the acknowledgement banner, and `/dashboard` bounces you back to
sign-in.

> **Watch this one closely.** The `authClient.deleteUser()` path is the one nothing in CI
> exercises — it is where the `freshAge` bug lived. To test the failure branch honestly, sign in,
> wait, and delete a *second* throwaway account more than 24h after signing in; with
> `freshAge: 0` it should still succeed.

**Verify the request half did exactly what it should — and nothing more:**

```sql
-- Marked, not removed.
SELECT id, owner_user_id, plan, deleted_at, stripe_subscription_id
  FROM billing_account WHERE deleted_at IS NOT NULL;

-- Exactly one purge record, nothing purged yet.
SELECT account_id, thread_prefixes, legacy_thread_ids,
       cardinality(blob_urls) AS blobs, stripe_cancelled_at,
       requested_at, started_at, purged_at, attempts, last_error
  FROM account_purge ORDER BY requested_at DESC;

-- NOTHING cascaded: the workspaces are still there for the purge to deal with.
SELECT count(*) FROM workspace WHERE account_id = '<account_id>';   -- expect ≥ 1
```

`blobs` should include the avatar you uploaded. If it is 0, the upload wasn't attributed and the
purge won't collect it — stop and investigate before step 3.

**Confirm the deleted account really is locked out:** in a private window, sign in again as the
throwaway. You should *not* reach the old data. (Resolution raises `CY001`, every route 401s.)

---

## Step 3 — the purge

The grace window is 7 days. Either wait, or force it.

**To force it — check first that yours is the only pending record:**

```sql
SELECT account_id, requested_at FROM account_purge WHERE purged_at IS NULL;
```

If that returns anything other than your test row, **stop**: lowering the grace window purges
every pending deletion, including real users' inside their recovery window.

If it is only yours: set `CALYPR_PURGE_GRACE_DAYS=0` on Railway, wait for redeploy, then:

```bash
curl -sS -X POST "$API/internal/gc/purge-accounts" -H "x-calypr-internal-key: $KEY"
# expect: {"purged":1,"failed":0,"considered":1}
```

**Then put `CALYPR_PURGE_GRACE_DAYS` back to 7 (or unset it) immediately.**

**Verify the destruction:**

```sql
-- The account row is gone; the audit trail outlives it, by design.
SELECT count(*) FROM billing_account WHERE id = '<account_id>';        -- expect 0
SELECT purged_at, cardinality(blob_urls) AS remaining,
       cardinality(blob_urls_failed) AS failed, last_error
  FROM account_purge WHERE account_id = '<account_id>';
-- expect: purged_at set, remaining 0, failed 0, last_error NULL
```

`failed > 0` means Vercel refused the delete — the account is gone but the objects are not. The
urls are in `blob_urls_failed` for manual cleanup.

**The check no test can do:** open the `blob_url` you noted in step 2a. It must now 404. If it
still loads, blob deletion silently failed even though `failed` is 0 — that is the single most
important thing this step proves.

**And confirm the checkpoints went:**

```sql
SELECT count(*) FROM checkpoints WHERE thread_id LIKE 'ws:<workspace_id>:%';  -- expect 0
```

**Finally, the returning-user property:** sign in again as the same throwaway GitHub account. You
should get a clean, empty account — not a lockout. (The purge frees the UNIQUE `owner_user_id`
slot; that is why it hard-deletes rather than tombstoning.)

---

## Step 4 — Stripe

Production uses **live** keys, so a genuine test costs real money. In preference order:

1. **100% -off coupon** on a throwaway account. Real subscription object, real cancellation, no
   charge. Recommended.
2. **Local API against Stripe test-mode keys.** Exercises the same code path at zero risk, but
   proves nothing about the production wiring.
3. **Real card, then refund.** Works; you are moving real money to test a code path.

Whichever you choose, verify:

- In the Stripe dashboard the subscription is **canceled** immediately — not "cancels at period
  end". Immediate is intentional and forfeits the paid remainder unprorated; the dialog says so.
- The **customer still exists.** We deliberately never delete it — invoices and tax records have
  to survive the account that generated them.
- `account_purge.stripe_cancelled_at` is set.

**Also test the failure branch**, because it is the one that protects users: with an account that
has a subscription, temporarily break the Stripe key on Railway and attempt a delete. Expect a
**502**, the message rendered inline in the dialog, and:

```sql
SELECT deleted_at FROM billing_account WHERE id = '<account_id>';  -- expect NULL
SELECT count(*) FROM account_purge WHERE account_id = '<account_id>';  -- expect 0
```

Nothing deleted, retry free. Then restore the key.

---

## Rollback

**Revert the code. Do not `alembic downgrade` in production** once anything has been deleted.
Dropping `deleted_at` makes every marked-but-unpurged account live again — with its subscription
already cancelled — and every purged one a broken shell that `account_purge` still names. The
downgrade docstring says the same thing.

Reverting #61 alone (leaving #60) is safe and is the right first move if the UI misbehaves: the
button disappears, the backend sits idle.

---

## Known limitations, accepted for this release

- **Blobs we cannot delete.** `packages/nodes/src/calypr_nodes/_assets.py` (image-node output)
  writes no `upload` row, and share-page uploads pass `workspace_id=None`
  (`routers/uploads.py`). Those objects survive deletion permanently and are unattributable. The
  danger copy says "uploads", not "all your files", on purpose. Follow-up: record both.
- **The purge claim is not concurrency-hardened.** `purge_accounts` selects `FOR UPDATE SKIP
  LOCKED` but commits per account, which releases those locks. Harmless with a single nightly
  caller; two concurrent callers could both pick up the same record. Don't run it from two places.
- **`attempts >= 5` records are left alone** with their `last_error`, for a human. Check
  periodically:

```sql
SELECT account_id, attempts, last_error FROM account_purge
 WHERE purged_at IS NULL AND attempts >= 5;
```
