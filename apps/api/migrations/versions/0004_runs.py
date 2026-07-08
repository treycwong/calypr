"""runs: `run` + `run_usage` metering tables + RLS (WEEK2 plan §B)

Revision ID: 0004_runs
Revises: 0003_user_workspaces
Create Date: 2026-07-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_runs"
down_revision: str | None = "0003_user_workspaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run",
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
        # Ad-hoc playground graphs / assist drafts have no saved agent → nullable, SET NULL.
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("thread_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),  # running|completed|errored
        sa.Column("source", sa.Text(), nullable=False),  # playground|share|api|assist
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_run_workspace_created",
        "run",
        ["workspace_id", sa.text("created_at DESC")],
    )
    # Same tenant-isolation pattern as `agent` (migration 0002).
    op.execute("ALTER TABLE run ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY run_tenant_isolation ON run "
        "USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)"
    )

    op.create_table(
        "run_usage",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalized off `run` so the RLS policy applies without a join to `run`.
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("node_id", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index("ix_run_usage_run", "run_usage", ["run_id"])
    op.execute("ALTER TABLE run_usage ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY run_usage_tenant_isolation ON run_usage "
        "USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS run_usage_tenant_isolation ON run_usage")
    op.drop_index("ix_run_usage_run", table_name="run_usage")
    op.drop_table("run_usage")
    op.execute("DROP POLICY IF EXISTS run_tenant_isolation ON run")
    op.drop_index("ix_run_workspace_created", table_name="run")
    op.drop_table("run")
