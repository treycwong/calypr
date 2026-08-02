"""subscription cycle columns — renewal date + cancel-pending for the Billing tab

Revision ID: 0015_subscription_cycle
Revises: 0014_credit_ledger
Create Date: 2026-08-02

The Billing tab shows a workspace its plan, its renewal/cancel date, and lets it open Stripe's
Customer Portal to cancel or change plan. Showing the cycle date in-app without a live Stripe
call on every page load means mirroring three fields off the `customer.subscription.*` webhook
we already process: the subscription id, when the current paid period ends, and whether a
cancellation is pending for the end of that period.

All three are nullable / defaulted, populated only for workspaces that have subscribed. No
backfill: existing rows (Free, beta, or Plus rows that predate this) start NULL and are filled
on the next subscription event (renewal, or a change made through the portal).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_subscription_cycle"
down_revision: str | None = "0014_credit_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace", sa.Column("stripe_subscription_id", sa.String(), nullable=True)
    )
    op.add_column(
        "workspace",
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "workspace",
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("workspace", "cancel_at_period_end")
    op.drop_column("workspace", "current_period_end")
    op.drop_column("workspace", "stripe_subscription_id")
