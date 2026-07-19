"""ORM models. Phase 0 ships only the tenant anchor (`workspace`).

Domain tables (agents, runs, knowledge bases, …) arrive in later phases and all carry a
`workspace_id` + RLS policy following the pattern established in the baseline migration.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from calypr_api.db.base import Base


class Workspace(Base):
    """A tenant. Maps 1:1 to a Clerk organization (org = tenant)."""

    __tablename__ = "workspace"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    clerk_org_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    # A user's personal workspace (= Better Auth user.id); NULL for the shared dev workspace.
    owner_user_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Agent(Base):
    """A saved agent: a name + its canvas GraphSpec (stored as JSONB)."""

    __tablename__ = "agent"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    graph_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Run(Base):
    """One agent execution (a `/runs` stream or an `/assist` draft). Written best-effort by
    `RunRecorder` — persistence never blocks or breaks the hot path (WEEK2 plan §B)."""

    __tablename__ = "run"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Nullable: the playground runs ad-hoc graphs that aren't saved agents; `/assist` has none.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent.id", ondelete="SET NULL"),
        nullable=True,
    )
    thread_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)  # running|completed|errored
    source: Mapped[str] = mapped_column(String, nullable=False)  # playground|share|api|assist
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RunUsage(Base):
    """Per-node/per-model token usage for one run. `workspace_id` is denormalized off `run`
    so the RLS policy applies without a join."""

    __tablename__ = "run_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("run.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    node_id: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")


class ConnectorCredential(Base):
    """A workspace's saved MCP connector + its envelope-encrypted secret (MCP-NODE-PLAN §5).

    The canvas stores only this row's `id` (a `mcp_connector_ref`), never a token — so a leaked
    GraphSpec yields a handle, not a credential. `secret_encrypted` is Fernet ciphertext
    (see `vault.py`); the plaintext is decrypted only server-side at run time and never returned
    to the client. RLS scopes every row to its workspace, same as `agent`."""

    __tablename__ = "connector_credential"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    # "mcp" (Tier B — user-supplied HTTP URL) | "notion" (Tier A — OAuth). Drives resolution.
    kind: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)  # user-facing label
    # Tier B: the MCP server URL. Tier A: unused (the URL comes from server config).
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    transport: Mapped[str] = mapped_column(
        String, nullable=False, server_default="streamable_http"
    )
    # Fernet ciphertext of the bearer/OAuth token; NULL for a keyless server. Never serialized.
    secret_encrypted: Mapped[str | None] = mapped_column(String, nullable=True)
    # Non-secret display metadata (e.g. Notion workspace name, discovered tool names snapshot).
    meta: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ShareLink(Base):
    """An unguessable, revocable link that lets a logged-out visitor run one agent without
    receiving its GraphSpec (WEEK3 plan §A). The anonymous run path resolves this table via
    the `share_agent_name` / `claim_share_run` SECURITY DEFINER functions, not the ORM."""

    __tablename__ = "share_link"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NULL ⇒ unlimited; the mint endpoint defaults to a finite cap for anonymous spend safety.
    run_cap: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
