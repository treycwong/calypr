"""conversations + messages + generated assets: durable Playground history and media

Until now a Playground transcript lived only in React state and the media a run generated left
no database row at all — `store_asset` returned a blob URL that existed nowhere but inside the
message markdown. LangGraph checkpoints hold the *agent's memory* of a conversation, but they are
TTL-collected per plan, carry no `workspace_id`, and are not searchable; they were never a
transcript. These four tables are.

`orphan_blob` is the small piece that makes "delete" honest: Vercel Blob shares no transaction
with Postgres, so a failed object delete has to be parked somewhere durable. `account_purge`
already does this for a *deleted account*; this is the same idea for a live workspace deleting
one conversation.

Revision ID: 0019_conversations_and_assets
Revises: 0018_plan_changed_at
Create Date: 2026-08-06
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_conversations_and_assets"
down_revision: str | None = "0018_plan_changed_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rls(table: str) -> None:
    """The tenant-isolation pattern every domain table carries (established in 0002/0004)."""
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY {table}_tenant_isolation ON {table} "
        "USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)"
    )


def upgrade() -> None:
    op.create_table(
        "conversation",
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
        # Same nullability as `run.agent_id`: the playground runs unsaved graphs.
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # **The suffix, never the composed thread id.** `threads.py` closed a cross-tenant hole
        # by making the `ws:<workspace>:` prefix always server-supplied; storing the composed id
        # in a table that gets read back out is how it drifts back into being trusted input.
        # Compose with `threads.workspace_thread()` at the two call sites that need it.
        sa.Column("thread_suffix", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
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
        # Makes the per-turn write an idempotent upsert rather than a select-then-insert race.
        sa.UniqueConstraint("workspace_id", "thread_suffix", name="uq_conversation_thread"),
    )
    op.create_index(
        "ix_conversation_workspace_updated",
        "conversation",
        ["workspace_id", sa.text("updated_at DESC")],
    )
    _rls("conversation")

    op.create_table(
        "message",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalized off `conversation` so RLS applies without a join — same as `run_usage`.
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Nullable: metering self-disables when the DB is unreachable, so there may be no run row.
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("run.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("role", sa.Text(), nullable=False),  # user|assistant
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        # Attachment URLs on a user turn, mirroring the client's `ChatMsg.images`.
        sa.Column(
            "images",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        # complete|partial|errored — assistant turns only. A run the user stopped mid-answer
        # keeps what streamed; dropping text the user watched arrive is worse than labelling it.
        sa.Column("status", sa.Text(), nullable=False, server_default="complete"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_message_conversation_seq", "message", ["conversation_id", "seq"])
    _rls("message")

    op.create_table(
        "asset",
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
        # CASCADE is deliberate: deleting a conversation deletes the media it produced, and the
        # confirm dialog says so. Nullable because a run may outlive its conversation row.
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversation.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("run.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agent.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("node_id", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),  # image|audio
        # **Always a real URL, never a `data:` URI.** The node only emits an asset event when the
        # blob upload actually succeeded (`StoredAsset.durable`), which is what keeps a multi-MB
        # base64 string out of Postgres and makes `delete_blob` on this column safe.
        sa.Column("blob_url", sa.Text(), nullable=False),
        sa.Column("pathname", sa.Text(), nullable=True),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=False, server_default="0"),
        # The alt text / caption the node already computes — what the Media tab searches.
        sa.Column("caption", sa.Text(), nullable=False, server_default=""),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_asset_workspace_created",
        "asset",
        ["workspace_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_asset_conversation", "asset", ["conversation_id"])
    _rls("asset")

    op.create_table(
        "orphan_blob",
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
        sa.Column("blob_url", sa.Text(), nullable=False),
        sa.Column(
            "failed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("ix_orphan_blob_failed_at", "orphan_blob", ["failed_at"])
    _rls("orphan_blob")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS orphan_blob_tenant_isolation ON orphan_blob")
    op.drop_index("ix_orphan_blob_failed_at", table_name="orphan_blob")
    op.drop_table("orphan_blob")

    op.execute("DROP POLICY IF EXISTS asset_tenant_isolation ON asset")
    op.drop_index("ix_asset_conversation", table_name="asset")
    op.drop_index("ix_asset_workspace_created", table_name="asset")
    op.drop_table("asset")

    op.execute("DROP POLICY IF EXISTS message_tenant_isolation ON message")
    op.drop_index("ix_message_conversation_seq", table_name="message")
    op.drop_table("message")

    op.execute("DROP POLICY IF EXISTS conversation_tenant_isolation ON conversation")
    op.drop_index("ix_conversation_workspace_updated", table_name="conversation")
    op.drop_table("conversation")
