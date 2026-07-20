"""provider_keys: per-workspace BYO model API keys (encrypted) + RLS

Revision ID: 0007_provider_keys
Revises: 0006_connectors
Create Date: 2026-07-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_provider_keys"
down_revision: str | None = "0006_connectors"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "provider_key",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("key_encrypted", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("workspace_id", "provider"),
    )

    # Same tenant-isolation pattern as `agent` (CLAUDE-PLAN.md §6).
    op.execute("ALTER TABLE provider_key ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY provider_key_tenant_isolation ON provider_key "
        "USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS provider_key_tenant_isolation ON provider_key")
    op.drop_table("provider_key")
