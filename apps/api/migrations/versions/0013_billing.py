"""billing: map a workspace to its Stripe customer, and make webhook delivery idempotent

Revision ID: 0013_billing
Revises: 0012_invite_granted_at
Create Date: 2026-07-23

Two things the payment → entitlement loop needs:

**`workspace.stripe_customer_id`** — a subscription event names a *customer*, not a workspace, so
without this there is no way to answer "whose plan changed?". Unique, because two workspaces
sharing a customer would make that answer ambiguous in exactly the case where money is involved.

**`stripe_event`** — Stripe guarantees *at-least-once* delivery: retries after a timeout, and
duplicates in normal operation. Recording each `event.id` before acting makes replay a no-op,
which matters because these handlers are not naturally idempotent — a redelivered
`customer.subscription.deleted` after a re-subscribe would otherwise downgrade a paying customer.

The credit ledger from `PRICING-SPEC.md` §4 is deliberately *not* here: credits are only
meaningful once metering debits them, and shipping an unused table invites drift. This migration
is the entitlement half — the part that makes the Plus button do something.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_billing"
down_revision: str | None = "0012_invite_granted_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspace", sa.Column("stripe_customer_id", sa.String(), nullable=True))
    op.create_unique_constraint(
        "uq_workspace_stripe_customer_id", "workspace", ["stripe_customer_id"]
    )

    op.create_table(
        "stripe_event",
        # Stripe's own event id (`evt_…`) is the primary key: the insert *is* the idempotency
        # check, so two concurrent deliveries can't both pass it.
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("stripe_event")
    op.drop_constraint("uq_workspace_stripe_customer_id", "workspace", type_="unique")
    op.drop_column("workspace", "stripe_customer_id")
