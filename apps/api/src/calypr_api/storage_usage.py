"""Measuring what an account stores, and reclaiming what it no longer needs.

**The byte figure is displayed, not enforced, and that is deliberate.** Three things make an
honest byte cap impossible to enforce today:

1. The dominant consumer is LangGraph's checkpoint tables, which are created by
   `AsyncPostgresSaver.setup()` outside Alembic, carry **no `workspace_id`**, and are reachable
   only by joining `run.thread_id`. A run's serialized state can be hundreds of KB.
2. Vercel Blob uploads wrote **no database row at all** before 0016, so bytes already spent are
   unrecoverable. `upload` starts the record from that migration forward and no earlier.
3. Measuring means summing `pg_column_size` over every graph and every checkpoint blob — an
   O(table) scan, fine nightly and impossible per request.

So the number is measured on a schedule and shown with the time it was taken. What actually
bounds storage is `gc_checkpoints` below: a per-plan TTL on run state. The figure on the Usage
tab is how a user sees that working, not a paywall.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from calypr_api import entitlements, threads

log = logging.getLogger(__name__)

#: Rough per-row costs for the fixed-width metering tables, including index overhead. Counted
#: rather than measured: `pg_column_size` over millions of narrow rows costs far more than the
#: precision is worth, and these are a rounding error next to graphs and checkpoints anyway.
_RUN_BYTES = 200
_RUN_USAGE_BYTES = 125
_LEDGER_BYTES = 120

#: Threads with no `run` row are anonymous playground traffic under the shared dev workspace.
#: They belong to no account, so no plan TTL applies — this is their absolute floor.
ORPHAN_THREAD_TTL_DAYS = 7

#: Threads swept per GC invocation. Batched so a nightly run has a bounded worst case and a
#: partial run is simply less progress rather than a long lock.
GC_BATCH_THREADS = 5_000


def measure_account(session: Session, account_id: uuid.UUID) -> int:
    """Total bytes attributable to this account, across all its workspaces.

    Best-effort by construction — see the module docstring for what is and isn't visible."""
    params = {"acc": str(account_id)}

    graphs = session.execute(
        text(
            """
            SELECT coalesce(sum(pg_column_size(a.graph_spec)), 0)
              FROM agent a JOIN workspace w ON w.id = a.workspace_id
             WHERE w.account_id = :acc
            """
        ),
        params,
    ).scalar_one()

    uploads = session.execute(
        text(
            """
            SELECT coalesce(sum(u.bytes), 0)
              FROM upload u JOIN workspace w ON w.id = u.workspace_id
             WHERE w.account_id = :acc
            """
        ),
        params,
    ).scalar_one()

    runs, run_usage = session.execute(
        text(
            """
            SELECT count(DISTINCT r.id), count(ru.id)
              FROM run r
              JOIN workspace w ON w.id = r.workspace_id
              LEFT JOIN run_usage ru ON ru.run_id = r.id
             WHERE w.account_id = :acc
            """
        ),
        params,
    ).one()

    ledger = session.execute(
        text("SELECT count(*) FROM credit_ledger WHERE account_id = :acc"), params
    ).scalar_one()

    # The big one, and the only part measured rather than estimated.
    #
    # Two ways in, because thread ids changed shape. Threads minted since `threads.py` carry
    # their workspace in the id, so a prefix match finds them with no join — and finds them even
    # when metering failed to write a `run` row, which is how real bytes used to end up belonging
    # to nobody. Older threads have no prefix and are still only reachable through `run`, so both
    # are summed; the union keeps a thread from being counted twice. The join arm can go once the
    # last pre-`threads.py` thread has aged out of the retention window.
    prefixes = [
        threads.workspace_prefix(row[0])
        for row in session.execute(
            text("SELECT id FROM workspace WHERE account_id = :acc"), params
        ).all()
    ]
    checkpoints = session.execute(
        text(
            """
            SELECT coalesce(sum(pg_column_size(b.blob)), 0)
              FROM checkpoint_blobs b
             WHERE b.thread_id IN (
                   SELECT c.thread_id FROM checkpoints c
                    WHERE c.thread_id LIKE ANY(:prefixes)
                   UNION
                   SELECT r.thread_id FROM run r
                     JOIN workspace w ON w.id = r.workspace_id
                    WHERE w.account_id = :acc AND r.thread_id IS NOT NULL)
            """
        ),
        {**params, "prefixes": [f"{p}%" for p in prefixes]},
    ).scalar_one()

    return int(
        graphs
        + uploads
        + checkpoints
        + runs * _RUN_BYTES
        + run_usage * _RUN_USAGE_BYTES
        + ledger * _LEDGER_BYTES
    )


def measure_all(session: Session) -> int:
    """Refresh `account.storage_bytes` for every account. Returns how many were measured."""
    ids = [row[0] for row in session.execute(text("SELECT id FROM billing_account")).all()]
    now = datetime.now(UTC)
    for account_id in ids:
        try:
            total = measure_account(session, account_id)
        except Exception:
            # One unmeasurable account must not stop the rest; its `storage_measured_at` simply
            # goes stale, which the UI already knows how to report.
            log.warning("storage measurement failed for account %s", account_id, exc_info=True)
            continue
        session.execute(
            text(
                "UPDATE billing_account SET storage_bytes = :b, storage_measured_at = :t"
                " WHERE id = :i"
            ),
            {"b": total, "t": now, "i": str(account_id)},
        )
    session.commit()
    return len(ids)


def _delete_threads(session: Session, thread_ids: list[str]) -> int:
    """Drop every checkpoint row for these threads, children first."""
    if not thread_ids:
        return 0
    deleted = 0
    # Order matters: `checkpoint_writes` and `checkpoint_blobs` reference the checkpoint rows,
    # and LangGraph owns these tables so there is no FK cascade to rely on.
    for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
        deleted += session.execute(
            text(f"DELETE FROM {table} WHERE thread_id = ANY(:ids)"),  # noqa: S608
            {"ids": thread_ids},
        ).rowcount
    return deleted


def gc_checkpoints(session: Session, *, batch: int = GC_BATCH_THREADS) -> dict[str, int]:
    """Delete run state past its plan's retention window.

    **This is what actually bounds storage.** Free keeps 7 days of run state, paid 30 — long
    enough to reopen yesterday's thread, short enough that a chatty agent doesn't accumulate
    forever in tables nothing else prunes.

    Idempotent and batched, so a partial run is safe to simply re-run."""
    ttl_cases = " ".join(
        f"WHEN a.plan = '{plan}' THEN interval '{lim.checkpoint_ttl_days} days'"
        for plan, lim in entitlements.LIMITS.items()
    )
    free_ttl = entitlements.limits(entitlements.FREE).checkpoint_ttl_days

    expired = [
        row[0]
        for row in session.execute(
            text(
                f"""
                SELECT DISTINCT r.thread_id
                  FROM run r
                  JOIN workspace w ON w.id = r.workspace_id
                  JOIN billing_account   a ON a.id = w.account_id
                 WHERE r.thread_id IS NOT NULL
                   AND r.created_at < now() - (CASE {ttl_cases}
                                               ELSE interval '{free_ttl} days' END)
                   -- Only threads that still have state to reclaim. `run` rows outlive their
                   -- checkpoints (run history is kept; the state is not), so without this every
                   -- already-swept thread matches forever and fills the batch, starving the
                   -- threads that do need collecting.
                   AND EXISTS (SELECT 1 FROM checkpoints c WHERE c.thread_id = r.thread_id)
                 LIMIT :batch
                """  # noqa: S608 — interpolated values come from our own LIMITS table
            ),
            {"batch": batch},
        ).all()
    ]
    rows = _delete_threads(session, expired)

    # Threads with no `run` row at all: anonymous playground and share traffic, which is never
    # attributed to an account. Without this they would accumulate forever, and they are exactly
    # the traffic nobody is paying for.
    #
    # `ws:`-prefixed threads are excluded even without a run row. They belong to a workspace by
    # construction (`threads.py`), so a missing run row means metering failed rather than that
    # nobody owns the conversation — and collecting a paying customer's thread after 7 days
    # because of *our* metering failure is the wrong way to be wrong. They stay until the
    # plan-TTL query above reaches them, or forever if their run row never lands; that is a
    # bounded leak and the safe direction.
    orphans = [
        row[0]
        for row in session.execute(
            text(
                """
                SELECT c.thread_id FROM checkpoints c
                 WHERE NOT EXISTS (SELECT 1 FROM run r WHERE r.thread_id = c.thread_id)
                   AND c.thread_id NOT LIKE 'ws:%'
                 GROUP BY c.thread_id
                HAVING max(c.checkpoint_id) < :floor
                 LIMIT :batch
                """
            ),
            # LangGraph checkpoint ids are UUIDv6-like and sort by time, so the oldest id of a
            # thread orders the same way its creation time would — there is no timestamp column.
            {"floor": _uuid6_floor(ORPHAN_THREAD_TTL_DAYS), "batch": batch},
        ).all()
    ]
    rows += _delete_threads(session, orphans)

    session.commit()
    return {"threads": len(expired) + len(orphans), "rows": rows}


def _uuid6_floor(days: int) -> str:
    """A UUIDv6 whose timestamp is `days` ago, for comparing against LangGraph checkpoint ids.

    The checkpoint tables carry no `created_at`, but `checkpoint_id` is time-ordered, so a
    synthetic id at the cutoff is what makes "older than N days" expressible at all."""
    cutoff = datetime.now(UTC).timestamp() - days * 86_400
    # UUIDv6 counts 100ns intervals since the Gregorian epoch (1582-10-15).
    ticks = int((cutoff + 12_219_292_800) * 10_000_000)
    hi, mid, lo = (ticks >> 28) & 0xFFFFFFFF, (ticks >> 12) & 0xFFFF, ticks & 0x0FFF
    return f"{hi:08x}-{mid:04x}-6{lo:03x}-8000-000000000000"
