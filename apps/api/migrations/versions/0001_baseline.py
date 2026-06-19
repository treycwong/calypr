"""baseline: pgvector extension + workspace tenant anchor + RLS scaffolding

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "workspace",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("clerk_org_id", sa.String(), nullable=True, unique=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # RLS scaffolding (CLAUDE-PLAN.md §6). Every tenant-scoped table follows this
    # pattern: enable RLS + a policy keyed on the per-session GUC `calypr.workspace_id`
    # (set via calypr_api.db.session.set_tenant). The `true` arg to current_setting
    # makes it return NULL (not error) when the GUC is unset, e.g. during migrations.
    # Full enforcement via a dedicated non-owner app role is hardened in a later phase.
    op.execute("ALTER TABLE workspace ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY workspace_self_isolation ON workspace "
        "USING (id = current_setting('calypr.workspace_id', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS workspace_self_isolation ON workspace")
    op.drop_table("workspace")
    # The `vector` extension is intentionally left installed.
