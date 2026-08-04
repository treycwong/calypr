"""Destroying the accounts that `DELETE /account` marked.

The request wrote down *what* must die (`account_purge`) and cancelled Stripe. This does the
crossing: Vercel Blob, then LangGraph's checkpoint tables, then one cascading delete of our own
rows. It runs from the nightly job and every step is safe to re-run.

**The ordering constraint that rots silently.** Thread ids were collected in the *request*, before
anything cascaded, and the checkpoints are deleted here **before** the cascade drops `run` and
`workspace`. Afterwards those threads are unreachable and **no GC arm covers them** —
`gc_checkpoints`'s orphan arm excludes `ws:%`, and its TTL arm joins run → workspace →
billing_account, all of which would be gone. Get this wrong and the bytes leak forever with zero
GC coverage, silently, for exactly the users who asked to be forgotten. `test_purge.py`'s headline
test exists to catch it.

**Blobs first, and a blob failure never blocks the database purge.** Vercel is the store we don't
control; if it is down or a token has rotated, the user's request to be deleted should still be
honoured. Failed urls are parked in `blob_urls_failed` where an operator can see them, rather than
retried forever or dropped.

**The grace window is the only recovery there is.** Once this runs there is no undo, and the user
cannot ask for one — their sign-in is gone. `CALYPR_PURGE_GRACE_DAYS` (Railway) buys the time.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from calypr_storage import BlobError, delete_blob
from sqlalchemy import text
from sqlalchemy.orm import Session

from calypr_api import storage_usage
from calypr_api.config import settings

log = logging.getLogger(__name__)

#: Blob urls deleted per request. Matches `calypr_storage`'s own chunk so one failure costs one
#: chunk's worth of progress.
BLOB_CHUNK = 100

#: Threads swept per statement while draining a prefix. Bounded so a huge account is many small
#: transactions rather than one enormous lock.
THREAD_BATCH = 1_000

#: After this many failed attempts a record is left alone with its `last_error`, for a human.
#: Without it, one record that reliably kills the worker retries every night forever — and,
#: worse, blocks nothing else from being noticed.
MAX_ATTEMPTS = 5


def purge_accounts(session: Session, *, limit: int = 10) -> dict[str, int]:
    """Purge up to `limit` accounts whose grace window has expired. Returns a small summary."""
    grace = settings.purge_grace_days
    rows = session.execute(
        text(
            """
            SELECT id, account_id, owner_user_id
              FROM account_purge
             WHERE purged_at IS NULL
               AND attempts < :max_attempts
               AND requested_at < now() - make_interval(days => :grace)
             ORDER BY requested_at
             LIMIT :limit
             FOR UPDATE SKIP LOCKED
            """
        ),
        {"grace": grace, "limit": limit, "max_attempts": MAX_ATTEMPTS},
    ).all()

    purged = 0
    failed = 0
    for row in rows:
        # Claim before doing any work, and **commit the claim immediately**. A record that
        # reliably kills this process would otherwise never record an attempt, and would be
        # retried forever with the same result every night.
        session.execute(
            text(
                "UPDATE account_purge SET attempts = attempts + 1, started_at = now()"
                " WHERE id = :i"
            ),
            {"i": str(row.id)},
        )
        session.commit()

        try:
            _purge_one(session, row.id, row.account_id)
            purged += 1
        except Exception as exc:  # one bad account must not stop the rest
            session.rollback()
            log.exception("purge failed for account %s", row.account_id)
            session.execute(
                text("UPDATE account_purge SET last_error = :e WHERE id = :i"),
                {"e": f"{type(exc).__name__}: {exc}"[:2000], "i": str(row.id)},
            )
            session.commit()
            failed += 1

    return {"purged": purged, "failed": failed, "considered": len(rows)}


def _purge_one(session: Session, purge_id: uuid.UUID, account_id: uuid.UUID) -> None:
    record = session.execute(
        text(
            "SELECT thread_prefixes, legacy_thread_ids, blob_urls"
            "  FROM account_purge WHERE id = :i"
        ),
        {"i": str(purge_id)},
    ).one()

    # 1. Blobs. Best-effort, and drained as we go so a crash resumes rather than re-issuing
    #    deletes for objects that are already gone.
    _purge_blobs(session, purge_id, list(record.blob_urls or []))

    # 2. Checkpoints — **before** the cascade, and mandatory. See the module docstring.
    for prefix in record.thread_prefixes or []:
        _drain_prefix(session, prefix)
    legacy = list(record.legacy_thread_ids or [])
    for start in range(0, len(legacy), THREAD_BATCH):
        storage_usage.delete_threads(session, legacy[start : start + THREAD_BATCH])
        session.commit()

    # 3. The cascade. One delete; `workspace` and everything under it goes with it (0016).
    #
    #    A hard delete, not a tombstone. `account_purge` is the audit trail, and removing the row
    #    frees the UNIQUE `owner_user_id` and `stripe_customer_id` slots — so someone who deletes
    #    their account and later comes back gets a clean signup instead of a permanent lockout.
    session.execute(
        text("DELETE FROM billing_account WHERE id = :a"), {"a": str(account_id)}
    )

    session.execute(
        text("UPDATE account_purge SET purged_at = now(), last_error = NULL WHERE id = :i"),
        {"i": str(purge_id)},
    )
    session.commit()
    log.info("purged account %s", account_id)


#: Remove `:chunk` from `blob_urls`. Postgres has no `array_subtract`, so this rebuilds the
#: column from the elements that aren't in the chunk. Written once and reused by both outcomes
#: below — a success and a failure differ only in whether the chunk is also *recorded*.
_DRAIN = (
    "SET blob_urls = (SELECT coalesce(array_agg(u), '{}')"
    "                   FROM unnest(blob_urls) u WHERE NOT (u = ANY(:chunk)))"
)


def _purge_blobs(session: Session, purge_id: uuid.UUID, urls: list[str]) -> None:
    """Delete `urls` in chunks, draining each chunk out of `blob_urls` as it is dealt with.

    Draining is what makes a crashed purge resumable: whatever is still in `blob_urls` on the
    next run is exactly what hasn't been handled, so nothing is re-issued and nothing is lost."""
    for start in range(0, len(urls), BLOB_CHUNK):
        chunk = urls[start : start + BLOB_CHUNK]
        try:
            asyncio.run(delete_blob(chunk))
            sql = f"UPDATE account_purge {_DRAIN} WHERE id = :i"
        except BlobError:
            # Park it and carry on. The account still gets deleted — a storage provider we don't
            # control must not be able to veto someone's deletion request — but the urls stay
            # visible so an operator can clean up, rather than the leak being invisible.
            log.warning(
                "blob delete failed for purge %s (%d urls); parking them",
                purge_id, len(chunk), exc_info=True,
            )
            sql = (
                f"UPDATE account_purge {_DRAIN},"
                "     blob_urls_failed = blob_urls_failed || :chunk"
                " WHERE id = :i"
            )
        session.execute(text(sql), {"chunk": chunk, "i": str(purge_id)})
        session.commit()


def _drain_prefix(session: Session, prefix: str) -> None:
    """Delete every checkpoint thread under `prefix`, a batch at a time until none are left."""
    while True:
        ids = [
            r[0]
            for r in session.execute(
                text(
                    "SELECT DISTINCT thread_id FROM checkpoints"
                    " WHERE thread_id LIKE :p || '%' LIMIT :batch"
                ),
                {"p": prefix, "batch": THREAD_BATCH},
            ).all()
        ]
        if not ids:
            return
        storage_usage.delete_threads(session, ids)
        session.commit()
