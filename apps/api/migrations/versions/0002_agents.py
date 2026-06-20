"""agents: seed a dev workspace + the agent table (GraphSpec storage) + RLS

Revision ID: 0002_agents
Revises: 0001_baseline
Create Date: 2026-06-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_agents"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEV_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # A fixed dev workspace so Phase 2 has a tenant to attach agents to (pre-Clerk).
    op.execute(
        f"INSERT INTO workspace (id, name) VALUES ('{DEV_WORKSPACE_ID}', 'Development') "
        "ON CONFLICT (id) DO NOTHING"
    )

    op.create_table(
        "agent",
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
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("graph_spec", postgresql.JSONB(), nullable=False),
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

    # Same tenant-isolation pattern as `workspace` (CLAUDE-PLAN.md §6).
    op.execute("ALTER TABLE agent ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY agent_tenant_isolation ON agent "
        "USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS agent_tenant_isolation ON agent")
    op.drop_table("agent")
