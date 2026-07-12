"""share_links: `share_link` table + RLS + anonymous SECURITY DEFINER resolvers (WEEK3 plan §A)

Revision ID: 0005_share_links
Revises: 0004_runs
Create Date: 2026-07-11

A share link lets a logged-out visitor run an owner's agent without ever receiving the
GraphSpec. The table is tenant-scoped like every other domain table (RLS on
`calypr.workspace_id`), but the *anonymous* run path has no tenant GUC set, so two
`SECURITY DEFINER` functions (pattern from `resolve_workspace` in 0003) read it safely:
`share_agent_name` (name only, never the spec) and `claim_share_run` (the atomic cap gate).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_share_links"
down_revision: str | None = "0004_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "share_link",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # NULL ⇒ unlimited (the API defaults to a finite cap; NULL is a deliberate owner choice).
        sa.Column("run_cap", sa.Integer(), nullable=True),
        sa.Column("run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("share_link_token_key", "share_link", ["token"])
    op.create_index("ix_share_link_workspace", "share_link", ["workspace_id"])
    # Same tenant-isolation pattern as `agent` (migration 0002) — scopes mint/list/revoke.
    op.execute("ALTER TABLE share_link ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY share_link_tenant_isolation ON share_link "
        "USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)"
    )

    # Anonymous reads: no per-request `calypr.workspace_id` GUC is set for a logged-out visitor,
    # so these run SECURITY DEFINER (pattern + pinned search_path from `resolve_workspace`).
    # `share_agent_name` returns the agent NAME only — never the spec.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION share_agent_name(p_token text)
        RETURNS text
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT a.name
            FROM share_link s
            JOIN agent a ON a.id = s.agent_id
            WHERE s.token = p_token AND s.revoked_at IS NULL;
        $$;
        """
    )

    # The atomic cap gate. A single conditional UPDATE (row-locked) both checks and increments,
    # so two concurrent runs can't both pass a cap of N. A row updated ⇒ 'ok' + the owner's
    # workspace + the agent's spec; otherwise a follow-up SELECT categorizes why (messaging only).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION claim_share_run(p_token text)
        RETURNS TABLE(status text, workspace_id uuid, agent_id uuid, graph_spec jsonb)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE
            claimed_agent uuid;
            claimed_ws uuid;
        BEGIN
            UPDATE share_link s
            SET run_count = s.run_count + 1
            WHERE s.token = p_token
              AND s.revoked_at IS NULL
              AND (s.run_cap IS NULL OR s.run_count < s.run_cap)
            RETURNING s.agent_id, s.workspace_id INTO claimed_agent, claimed_ws;

            IF FOUND THEN
                RETURN QUERY
                    SELECT 'ok'::text, claimed_ws, claimed_agent, a.graph_spec
                    FROM agent a WHERE a.id = claimed_agent;
                RETURN;
            END IF;

            -- No row claimed: say why (for the SSE error message only).
            IF NOT EXISTS (SELECT 1 FROM share_link s WHERE s.token = p_token) THEN
                RETURN QUERY SELECT 'not_found'::text, NULL::uuid, NULL::uuid, NULL::jsonb;
            ELSIF EXISTS (
                SELECT 1 FROM share_link s
                WHERE s.token = p_token AND s.revoked_at IS NOT NULL
            ) THEN
                RETURN QUERY SELECT 'revoked'::text, NULL::uuid, NULL::uuid, NULL::jsonb;
            ELSE
                RETURN QUERY SELECT 'cap'::text, NULL::uuid, NULL::uuid, NULL::jsonb;
            END IF;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS claim_share_run(text)")
    op.execute("DROP FUNCTION IF EXISTS share_agent_name(text)")
    op.execute("DROP POLICY IF EXISTS share_link_tenant_isolation ON share_link")
    op.drop_index("ix_share_link_workspace", table_name="share_link")
    op.drop_constraint("share_link_token_key", "share_link", type_="unique")
    op.drop_table("share_link")
