"""workspace.assistant_model — per-workspace default model for the AI assistant

Revision ID: 0009_assistant_model
Revises: 0008_plan_and_waitlist
Create Date: 2026-07-21

Until now the assistant's model was a single server-wide env var (`CALYPR_ASSISTANT_MODEL`), so
trying a different one meant a redeploy. This column lets a workspace pick its own from the
allow-list in `calypr_api.assistant_models`, chosen in Settings → Workspace.

Empty string (the default) means "inherit the server default" — deliberately not NULL, so the
column has one falsy value rather than two, and existing rows keep exactly today's behaviour.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_assistant_model"
down_revision: str | None = "0008_plan_and_waitlist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace",
        sa.Column(
            "assistant_model", sa.String(), nullable=False, server_default=sa.text("''")
        ),
    )


def downgrade() -> None:
    op.drop_column("workspace", "assistant_model")
