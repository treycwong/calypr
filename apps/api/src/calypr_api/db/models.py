"""ORM models. Phase 0 ships only the tenant anchor (`workspace`).

Domain tables (agents, runs, knowledge bases, …) arrive in later phases and all carry a
`workspace_id` + RLS policy following the pattern established in the baseline migration.
"""

from __future__ import annotations

import uuid
from datetime import date as dt_date
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from calypr_api.db.base import Base


class Account(Base):
    """Who pays. One per signed-in user, owning one or more workspaces (0016_accounts).

    The split with `Workspace` is **who pays vs. where work lives**. Everything that must not
    multiply when a user creates a second workspace lives here: the plan, the Stripe customer and
    subscription, the credit balance, the storage figure. Quotas — projects, credits, storage —
    are therefore pooled across an account's workspaces by construction rather than by remembering
    to sum them.

    Account ids were seeded from the workspace ids they replaced, so a Stripe checkout session
    minted before that migration still resolves. See the 0016 docstring before changing how ids
    are assigned."""

    __tablename__ = "billing_account"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # = Better Auth user.id; NULL for the shared dev account. No FK — the `user` table belongs to
    # Better Auth, not Alembic (the reasoning 0003 set out and 0016 kept).
    owner_user_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    # Entitlement tier: `free | beta | plus`. Read through `calypr_api.entitlements` rather than
    # compared inline, so gating rules live in one place.
    plan: Mapped[str] = mapped_column(String, nullable=False, server_default="free")
    # The Stripe customer this account bills as. Subscription events name a customer, not an
    # account, so this is what maps a payment back to whose plan should change. Unique: two
    # accounts on one customer would make that mapping ambiguous.
    stripe_customer_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    # --- Subscription cycle (for the Billing tab) --------------------------------------------
    # Mirrored from Stripe's `customer.subscription.*` events so the Billing tab can show the
    # renewal/cancel date without a live Stripe call on every page load. NULL for an account
    # that has never subscribed (Free, or `beta`). `current_period_end` is when the current paid
    # period ends — the renewal date, or the cutoff date once `cancel_at_period_end` is set.
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    # Cached credit balance in micro-credits (1 credit = 1,000 micro). The `credit_ledger` is
    # the truth; this is kept in the same transaction so the hot path reads one column instead
    # of summing every row. `credits.recompute_balance` repairs drift in the ledger's favour.
    credit_balance_micro: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="0"
    )
    # The month whose grant has been issued — makes "already granted this cycle?" a comparison
    # rather than a scan.
    grant_cycle_anchor: Mapped[dt_date | None] = mapped_column(Date, nullable=True)
    # Bytes this account is using, as of `storage_measured_at`. Written by the nightly job in
    # `storage_usage.py` — never on the hot path, because measuring it means summing
    # `pg_column_size` over every graph and checkpoint blob. NULL `storage_measured_at` means
    # never measured, which the UI reports honestly rather than showing a confident 0 B.
    storage_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    storage_measured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Workspace(Base):
    """Where work lives: a named container for agents, runs and connectors.

    The unit the RLS GUC (`calypr.workspace_id`) scopes to, and the unit a request resolves to —
    so every domain table below stays workspace-scoped and their policies were untouched by the
    account split. What a workspace no longer owns is anything to do with money; that moved to
    `Account` in 0016 so three workspaces don't mean three subscriptions.

    `clerk_org_id` is vestigial — Clerk was never wired up, Better Auth is what runs."""

    __tablename__ = "workspace"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    clerk_org_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("billing_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    # Which model the AI assistant drafts graphs with, chosen in Settings → Workspace. Empty
    # string = inherit `CALYPR_ASSISTANT_MODEL` (the server default); validated on write against
    # `calypr_api.assistant_models.ASSISTANT_MODELS`.
    assistant_model: Mapped[str] = mapped_column(String, nullable=False, server_default="")
    # The model this workspace's LLM *nodes* run on when they don't name one themselves
    # (node configs ship `model: ""`). Empty = `PLATFORM_DEFAULT_MODEL` (gpt-4o-mini).
    # Same allow-list as `assistant_model`; resolved into runs and codegen by
    # `calypr_api.workspace_model.apply_default_model`.
    default_model: Mapped[str] = mapped_column(String, nullable=False, server_default="")
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
    transport: Mapped[str] = mapped_column(String, nullable=False, server_default="streamable_http")
    # Fernet ciphertext of the bearer/OAuth token; NULL for a keyless server. Never serialized.
    secret_encrypted: Mapped[str | None] = mapped_column(String, nullable=True)
    # Non-secret display metadata (e.g. Notion workspace name, discovered tool names snapshot).
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ProviderKey(Base):
    """A workspace's BYO API key for a model provider (openai / anthropic / tavily / …).

    One row per (workspace, provider). `key_encrypted` is Fernet ciphertext (see `vault.py`),
    decrypted only server-side at run time and injected into the model factory — it overrides
    the server env for that provider. Never returned to the client. RLS-scoped like `agent`."""

    __tablename__ = "provider_key"
    __table_args__ = (UniqueConstraint("workspace_id", "provider"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)  # openai|anthropic|tavily|…
    key_encrypted: Mapped[str] = mapped_column(String, nullable=False)
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


class Waitlist(Base):
    """A pre-signup email from the landing form.

    The one domain table with **no** `workspace_id` and no RLS tenant policy: rows are written by
    unauthenticated visitors who don't have a workspace yet (see 0008_plan_and_waitlist). It is
    write-only through the public endpoint — `POST /waitlist` never returns rows — and readable
    only via the admin-token route."""

    __tablename__ = "waitlist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # Normalized (trimmed + lowercased) by the API before insert, so uniqueness is meaningful.
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="landing")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Set when this address is invited into the beta.
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Set when that invite was actually redeemed (the owner signed in and got `beta`). An invite
    # is a one-time key: without this the auto-grant re-ran on every sign-in, so demoting anyone
    # back to `free` — trial over, beta over — silently undid itself at their next login.
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StripeEvent(Base):
    """One webhook delivery we've already acted on.

    Stripe guarantees *at-least-once* delivery — it retries on timeout and can duplicate in
    normal operation — and these handlers are not naturally idempotent: a redelivered
    `customer.subscription.deleted` arriving after someone re-subscribed would downgrade a paying
    customer. Stripe's own `evt_…` id is the primary key, so the insert *is* the idempotency
    check and two concurrent deliveries can't both pass it.

    No `workspace_id`: an event may arrive for a customer we can't map, and the row still has to
    be recorded so the retry stops."""

    __tablename__ = "stripe_event"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CreditLedger(Base):
    """One credit movement: a grant, a debit for a run, a top-up, or a manual adjustment.

    Append-only and signed — the balance is `SUM(delta_micro)`. Keeping the history rather than
    just a counter is what makes "why is my balance this?" answerable, which matters the first
    time a customer disputes a charge.

    `ref_id` is what makes a grant idempotent: unique per account for `kind='grant'`, so a
    redelivered `invoice.paid` cannot grant twice."""

    __tablename__ = "credit_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    #: Whose balance this moves. The account, not the workspace — credits pool across an
    #: account's workspaces, so this is the column the balance is summed over.
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_account.id", ondelete="CASCADE"), nullable=False
    )
    #: **Provenance, not the balance key**: which workspace spent this. Nullable because a grant
    #: or a Stripe top-up belongs to the account and happened in no particular workspace. Kept
    #: (rather than dropped in 0016) so a per-workspace usage breakdown stays possible without
    #: another migration.
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspace.id", ondelete="CASCADE"), nullable=True
    )
    #: Signed micro-credits: + grant/top-up, − debit.
    delta_micro: Mapped[int] = mapped_column(BigInteger, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # grant|debit|topup|adjust
    source: Mapped[str | None] = mapped_column(String, nullable=True)  # run|assist|share|stripe
    ref_id: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Upload(Base):
    """A file a workspace pushed to Vercel Blob.

    The bytes live in Blob, not here; this row exists so they are *attributable*. Before 0016 an
    upload wrote no database row at all, which meant no per-account storage figure could include
    them and nothing could ever reclaim an orphaned object. This table starts that record — blobs
    written before it remain unaccounted for, and there is no way to recover them."""

    __tablename__ = "upload"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    blob_url: Mapped[str] = mapped_column(String, nullable=False)
    pathname: Mapped[str] = mapped_column(String, nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
