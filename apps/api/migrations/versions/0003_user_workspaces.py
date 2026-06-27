"""user_workspaces: a personal workspace per user + resolve_workspace()

Revision ID: 0003_user_workspaces
Revises: 0002_agents
Create Date: 2026-06-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_user_workspaces"
down_revision: str | None = "0002_agents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Each signed-in user gets one personal workspace (owner_user_id = Better Auth user.id).
    # No FK to the Better-Auth-managed `user` table — avoid cross-tool migration coupling.
    op.add_column("workspace", sa.Column("owner_user_id", sa.String(), nullable=True))
    op.create_unique_constraint(
        "workspace_owner_user_id_key", "workspace", ["owner_user_id"]
    )

    # Atomic find-or-create of a user's personal workspace. SECURITY DEFINER so it runs before
    # the per-request tenant GUC is set (and regardless of the app role's RLS status). The
    # no-op ON CONFLICT update makes RETURNING yield the existing row id on a race.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION resolve_workspace(p_user_id text)
        RETURNS uuid
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE ws uuid;
        BEGIN
            INSERT INTO workspace (owner_user_id, name)
            VALUES (p_user_id, 'Personal')
            ON CONFLICT (owner_user_id) DO UPDATE SET name = workspace.name
            RETURNING id INTO ws;
            RETURN ws;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS resolve_workspace(text)")
    op.drop_constraint("workspace_owner_user_id_key", "workspace", type_="unique")
    op.drop_column("workspace", "owner_user_id")
