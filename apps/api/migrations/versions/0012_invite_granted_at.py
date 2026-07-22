"""waitlist.granted_at — an invite is a one-time key, not a standing entitlement

Revision ID: 0012_invite_granted_at
Revises: 0011_repair_saved_fake_models
Create Date: 2026-07-22

`grant_beta_if_invited` upgraded any `free` workspace whose owner was on the invite list, and it
re-ran on **every** sign-in. So a demotion could never stick: move someone from `beta` back to
`free` — when their trial ends, or when the beta itself ends — and their next login silently put
them back on `beta`. The manual admin route was documented as authoritative and quietly wasn't.

`granted_at` records that the invite has been redeemed. The auto-grant now fires only for an
invite that is stamped *and* unredeemed, so it does what an invite should: work once.

Existing rows are backfilled `granted_at = invited_at` — every invited address in production has
already signed in and been granted, so treating those invites as spent is the accurate reading,
and it means today's plans stop being overwritten the moment this ships.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_invite_granted_at"
down_revision: str | None = "0011_repair_saved_fake_models"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "waitlist", sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute("UPDATE waitlist SET granted_at = invited_at WHERE invited_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column("waitlist", "granted_at")
