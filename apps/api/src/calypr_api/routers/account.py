"""`DELETE /account` — the request half of account deletion.

**Scope.** This deletes the whole *account*: every workspace, every project, the runs, the
uploads, the credit balance, and the Stripe subscription. It is not "delete project" (on the
project card) or "delete workspace" (#59).

**What this route does and doesn't do.** It cancels Stripe synchronously, writes down everything
that still has to be destroyed (`account_purge`), and marks the account. It **cascades nothing** —
no workspace, run or checkpoint row is touched here. The actual destruction is `purge.py`, run
from the nightly job, because it crosses stores that share no transaction with Postgres.

That split is what makes the operation survivable. The one thing that genuinely cannot be undone
or retried is the Stripe cancellation, so it happens *first*, and if it fails nothing else is
written at all.

**Order matters and is asserted by tests.** Thread ids are collected *here*, before anything
cascades — afterwards the pre-prefix threads are unreachable and **no GC arm covers them**
(`gc_checkpoints`'s orphan arm excludes `ws:%`, and its TTL arm joins run → workspace →
billing_account, all of which would be gone). Get this wrong and the bytes leak forever.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import stripe
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from calypr_api import billing, threads
from calypr_api.accounts import account_for_workspace
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import AccountPurge
from calypr_api.deps import Tenant, tenant
from calypr_api.schemas import AccountDeleted

log = logging.getLogger(__name__)

router = APIRouter(tags=["account"])


@router.delete("/account", response_model=AccountDeleted)
def delete_account(t: Tenant = Depends(tenant)) -> AccountDeleted:
    """Cancel the subscription, record what must be destroyed, and mark the account deleted."""
    # 0. Dev/CI carve-out, **first**. The dev account is seeded by 0016 and shared by every
    #    anonymous request, local run and e2e test; marking it deleted would break CI
    #    permanently and there would be no way back short of a migration. 501 rather than 403:
    #    this isn't a permission problem, the operation genuinely does not exist here. The web
    #    proxy translates it, so the UI flow stays testable.
    if not settings.internal_key or str(t.workspace_id) == DEV_WORKSPACE_ID:
        raise HTTPException(status_code=501, detail="account deletion is disabled in dev mode")

    account = account_for_workspace(t.session, t.workspace_id)
    if account is None:
        raise HTTPException(status_code=404, detail="account not found")

    # 1. Idempotent. A double-submit, a retried request, or a user who came back to a stale tab
    #    all land here; none of them should be an error, and none should enqueue a second purge.
    if account.deleted_at is not None:
        return AccountDeleted(deleted=True, mode="live")

    # 2. Stripe, before anything is written. **On failure, change nothing and 502.** An account
    #    that no longer exists while its card keeps being charged is the one failure mode we
    #    cannot ship; since no row has been touched, the user can simply try again, and the
    #    dialog shows this message inline.
    cancelled_at: datetime | None = None
    try:
        if billing.cancel_subscription(account):
            cancelled_at = datetime.now(UTC)
    except stripe.StripeError:
        log.exception("could not cancel subscription for account %s; aborting delete", account.id)
        raise HTTPException(
            status_code=502,
            detail=(
                "We couldn't cancel your subscription, so nothing was deleted."
                " Please try again."
            ),
        ) from None

    # 3. Collect, record and mark — one transaction.
    workspace_ids = [
        str(r[0])
        for r in t.session.execute(
            text("SELECT id FROM workspace WHERE account_id = :a"), {"a": str(account.id)}
        )
    ]
    share_tokens = [
        r[0]
        for r in t.session.execute(
            text(
                "SELECT s.token FROM share_link s"
                " JOIN workspace w ON w.id = s.workspace_id"
                " WHERE w.account_id = :a"
            ),
            {"a": str(account.id)},
        )
    ]
    prefixes = [threads.workspace_prefix(w) for w in workspace_ids]
    prefixes += [threads.share_prefix(tok) for tok in share_tokens]

    # Threads predating `threads.py`'s namespacing carry neither prefix, so a LIKE match can't
    # find them and `run.thread_id` is the only remaining pointer. Collected now because the
    # cascade drops `run`.
    legacy = [
        r[0]
        for r in t.session.execute(
            text(
                "SELECT DISTINCT r.thread_id FROM run r"
                " JOIN workspace w ON w.id = r.workspace_id"
                " WHERE w.account_id = :a AND r.thread_id IS NOT NULL"
                "   AND r.thread_id NOT LIKE 'ws:%' AND r.thread_id NOT LIKE 'share:%'"
            ),
            {"a": str(account.id)},
        )
    ]

    # **The join through `workspace.account_id` is load-bearing.** It is the only thing
    # guaranteeing we never point a permanent, unrecoverable delete at a blob this account does
    # not own. Never widen this to a pathname or prefix match.
    #
    # Both halves matter: `upload` is what the user pushed in, `asset` is the media their runs
    # generated. Assets bill exactly like uploads, and they are the larger of the two — an image
    # run writes megabytes. Omitting them would leave a deleted account's blobs billing forever
    # with no GC arm anywhere that could ever find them, since the rows they were reachable
    # through are gone by then.
    blob_urls = [
        r[0]
        for r in t.session.execute(
            text(
                "SELECT u.blob_url FROM upload u"
                " JOIN workspace w ON w.id = u.workspace_id"
                " WHERE w.account_id = :a"
                " UNION ALL "
                "SELECT a2.blob_url FROM asset a2"
                " JOIN workspace w2 ON w2.id = a2.workspace_id"
                " WHERE w2.account_id = :a"
                " UNION ALL "
                # Blobs a live delete already failed on. They are still billing and this is the
                # last moment anything can name them.
                "SELECT o.blob_url FROM orphan_blob o"
                " JOIN workspace w3 ON w3.id = o.workspace_id"
                " WHERE w3.account_id = :a"
            ),
            {"a": str(account.id)},
        )
    ]

    t.session.add(
        AccountPurge(
            account_id=account.id,
            owner_user_id=account.owner_user_id,
            thread_prefixes=prefixes,
            legacy_thread_ids=legacy,
            blob_urls=blob_urls,
            stripe_customer_id=account.stripe_customer_id,
            stripe_subscription_id=account.stripe_subscription_id,
            stripe_cancelled_at=cancelled_at,
        )
    )

    # `AND owner_user_id IS NOT NULL` is belt and braces over the step-0 carve-out: the dev
    # account is the one row with a NULL owner, so even a future refactor that lets a dev request
    # reach this far still cannot mark it.
    t.session.execute(
        text(
            "UPDATE billing_account"
            "   SET deleted_at = now(), plan = 'free', stripe_subscription_id = NULL,"
            "       current_period_end = NULL, cancel_at_period_end = false"
            " WHERE id = :a AND owner_user_id IS NOT NULL"
        ),
        {"a": str(account.id)},
    )

    # Drop the beta invite while we still legitimately hold the address — `account_purge` stores
    # no email, so after this transaction there is nothing left to match on. A returning user
    # signs up fresh rather than silently re-inheriting a beta grant.
    if t.email:
        t.session.execute(
            text("DELETE FROM waitlist WHERE lower(email) = lower(:e)"), {"e": t.email}
        )

    t.session.commit()
    log.info(
        "account %s marked deleted: %d prefixes, %d legacy threads, %d blobs",
        account.id, len(prefixes), len(legacy), len(blob_urls),
    )
    return AccountDeleted(deleted=True, mode="live")
