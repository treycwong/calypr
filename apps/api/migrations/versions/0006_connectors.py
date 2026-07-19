"""connectors: connector_credential (encrypted MCP/OAuth secrets) + RLS

Revision ID: 0006_connectors
Revises: 0005_share_links
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_connectors"
down_revision: str | None = "0005_share_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_credential",
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
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column(
            "transport",
            sa.String(),
            server_default="streamable_http",
            nullable=False,
        ),
        sa.Column("secret_encrypted", sa.String(), nullable=True),
        sa.Column(
            "meta", postgresql.JSONB(), server_default="{}", nullable=False
        ),
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
    )

    # Same tenant-isolation pattern as `agent` (CLAUDE-PLAN.md §6).
    op.execute("ALTER TABLE connector_credential ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY connector_credential_tenant_isolation ON connector_credential "
        "USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS connector_credential_tenant_isolation "
        "ON connector_credential"
    )
    op.drop_table("connector_credential")
