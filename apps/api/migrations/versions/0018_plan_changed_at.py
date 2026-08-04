"""record when a plan last changed, so a downgrade stops destroying run state on the same night

Revision ID: 0018_plan_changed_at
Revises: 0017_account_deletion
Create Date: 2026-08-04

`gc_checkpoints` derives its retention window from the account's plan **at collection time** and
had no idea when that plan became true. So the moment a subscription lapsed, every checkpoint
between the paid TTL (30 days) and the free one (7) was already expired, and the next nightly run
deleted it — silently, irreversibly, as a side effect of a billing event the user may not even
have noticed had completed.

This column is what lets the collector tell "Free, and has been for months" apart from "Free as of
an hour ago". `entitlements.retention_days` reads it and keeps the longer window open for
`DOWNGRADE_GRACE_DAYS` after a change, so there is time to re-subscribe or export before anything
is lost.

**Nullable, and NULL means "not recently changed".** Backfilling `created_at` would be a lie
(plenty of accounts have never changed plan) and backfilling `now()` would hand every existing
account a grace window it didn't earn. NULL reads as "no recent change", which is the truth for
every row that exists today and the safe answer for the collector.

Only `billing.set_plan` writes it, and only when the plan actually differs — so a redelivered
Stripe webhook, or a `cancel_at_period_end` flip that leaves the plan alone, does not extend
anyone's window.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_plan_changed_at"
down_revision: str | None = "0017_account_deletion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "billing_account",
        sa.Column("plan_changed_at", sa.DateTime(timezone=True), nullable=True),
    )
    # No index. The only reader is the nightly GC, which already scans `run` joined to the
    # account; a partial index on a column that is NULL for almost every row would cost writes
    # on every plan change and save nothing on the one query that reads it.


def downgrade() -> None:
    """Safe to run. Dropping this column reverts the collector to the pre-0018 behaviour — a
    downgrade once again expires 7-to-30-day-old run state immediately — but destroys nothing by
    itself."""
    op.drop_column("billing_account", "plan_changed_at")
