"""Repair saved agents that still carry the `fake` model

Revision ID: 0011_repair_saved_fake_models
Revises: 0010_default_model
Create Date: 2026-07-22

Four templates shipped with `model: "fake"` — the keyless test seam that answers "Echo: …" —
and anyone who saved one kept that value in their stored `graph_spec`. Fixing the templates and
the block defaults (0010) doesn't reach those rows: a saved agent runs what it was saved with,
so it would echo forever.

This rewrites `fake` → `""` (inherit) on LLM nodes only, so those agents pick up the workspace
default like everything else. An explicitly chosen *real* model is left alone — that's a
decision, not a default — and Image/Voice nodes are untouched (different seam, different ids).

Safe to run now because the app has no users beyond the founder; a rewrite of user-authored data
would deserve more ceremony than a migration otherwise.

Downgrade is a no-op: restoring `fake` would mean deliberately re-breaking the agents this fixes,
and the pre-migration value isn't worth preserving.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from calypr_api.workspace_model import strip_fake_models

revision: str = "0011_repair_saved_fake_models"
down_revision: str | None = "0010_default_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, graph_spec FROM agent")).fetchall()
    agents = nodes = 0
    for agent_id, spec in rows:
        # psycopg returns jsonb as a dict; tolerate a text column too.
        spec = json.loads(spec) if isinstance(spec, str) else spec
        if not isinstance(spec, dict):
            continue
        patched, changed = strip_fake_models(spec)
        if changed:
            conn.execute(
                sa.text("UPDATE agent SET graph_spec = :spec WHERE id = :id"),
                {"spec": json.dumps(patched), "id": agent_id},
            )
            agents += 1
            nodes += changed
    log.info("repaired %s node(s) across %s saved agent(s)", nodes, agents)


def downgrade() -> None:
    """Deliberately empty — see the module docstring."""
