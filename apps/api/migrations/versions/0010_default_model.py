"""workspace.default_model — the model LLM nodes use when they don't name one

Revision ID: 0010_default_model
Revises: 0009_assistant_model
Create Date: 2026-07-22

Sibling of `assistant_model` (0009), for the *canvas* rather than the assistant. Node configs
now ship `model: ""` (inherit), so the model a graph runs on is a workspace preference chosen
once in Settings → Workspace instead of a field to set on every block.

Empty string (the default) means "use the platform default" — `PLATFORM_DEFAULT_MODEL`,
currently `gpt-4o-mini`. Deliberately not NULL, matching 0009: one falsy value, not two.

Existing rows are unaffected: a saved agent whose nodes name a model explicitly keeps it, since
an explicit choice always wins over the inherited one.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_default_model"
down_revision: str | None = "0009_assistant_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace",
        sa.Column("default_model", sa.String(), nullable=False, server_default=sa.text("''")),
    )


def downgrade() -> None:
    op.drop_column("workspace", "default_model")
