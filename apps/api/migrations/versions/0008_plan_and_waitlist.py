"""workspace.plan (entitlements) + waitlist capture

Revision ID: 0008_plan_and_waitlist
Revises: 0007_provider_keys
Create Date: 2026-07-21

Two additions that together let a feature be opened to a cohort rather than to everyone:

- `workspace.plan` — the entitlement primitive (`free|beta|plus`). `PRICING-SPEC.md` §4 planned
  `free|plus` for the Week-9 billing migration; `beta` is the extra rung used to run a closed
  beta before anything is charged for. Billing (Stripe ids, credit ledger) still lands later —
  this is deliberately only the column that gating reads.
- `waitlist` — the landing-page form previously discarded submissions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_plan_and_waitlist"
down_revision: str | None = "0007_provider_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing rows become `free`; NOT NULL is safe because of the server default.
    op.add_column(
        "workspace",
        sa.Column("plan", sa.String(), nullable=False, server_default=sa.text("'free'")),
    )

    op.create_table(
        "waitlist",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default=sa.text("'landing'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Stamped when the address is invited into the beta — makes "who did we let in, when"
        # answerable without a separate audit table.
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("email", name="waitlist_email_key"),
    )

    # NOTE — deliberate RLS exception. Every other domain table carries `workspace_id` and the
    # `calypr.workspace_id` tenant policy (see 0007_provider_keys). `waitlist` cannot: rows are
    # written by unauthenticated visitors who have no workspace yet. It is therefore write-only
    # at the API layer (`POST /waitlist` never returns rows) and readable only by the
    # admin-token route. Same shape of documented exception as the share-link token lookup.


def downgrade() -> None:
    op.drop_table("waitlist")
    op.drop_column("workspace", "plan")
