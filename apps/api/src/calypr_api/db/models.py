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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
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
    # When `plan` last actually changed (0018). NULL = never, or not since the column existed.
    # Written only by `billing.set_plan`, and only on a real change, so a redelivered webhook
    # can't extend the window it opens: `entitlements.retention_days` keeps the *longer*
    # checkpoint TTL alive for a grace period after a downgrade, which is the only thing standing
    # between a lapsed subscription and run state being collected that same night.
    plan_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    # Set by `DELETE /account`; the row itself is removed later by the purge job (0017). While
    # this is non-NULL the account still exists in every table, but `resolve_account` refuses to
    # return it, so no request can reach it — see `deps.is_account_deleted`. The grace window
    # between the two is the only recovery path there is.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


class Conversation(Base):
    """One Playground conversation — the durable transcript, not the agent's memory of it.

    LangGraph's checkpoints are the memory: they hold the state a graph resumes from, they are
    TTL-collected per plan, and they carry no `workspace_id`. This row and its `Message` children
    are the record the *user* owns — kept until they delete it, searchable, and independent of
    whether the checkpoint has aged out.

    **`thread_suffix` is the suffix, never the composed thread id.** `threads.py` documents why
    the `ws:<workspace>:` prefix must always be server-supplied; compose with
    `threads.workspace_thread()` where a full id is needed. `(workspace_id, thread_suffix)` is
    unique, which is what lets the per-turn write be a single idempotent upsert."""

    __tablename__ = "conversation"
    __table_args__ = (
        UniqueConstraint("workspace_id", "thread_suffix", name="uq_conversation_thread"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Nullable for the same reason as `Run.agent_id`: the playground runs unsaved graphs.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent.id", ondelete="SET NULL"),
        nullable=True,
    )
    thread_suffix: Mapped[str] = mapped_column(Text, nullable=False)
    # Derived from the first user message; set only on insert, so a rename survives the next turn.
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Last activity — the list's sort key, bumped on every turn.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Message(Base):
    """One turn in a `Conversation`. `workspace_id` is denormalized off `conversation` so the
    RLS policy applies without a join, exactly as `run_usage` does off `run`.

    `status` matters on assistant turns: a run the user stopped mid-answer, or one that errored,
    keeps the text that actually streamed and is labelled `partial`/`errored`. Silently dropping
    output the user watched arrive is the worse failure. Only what the *server* streamed is
    stored — the ⚠️ and ℹ️ prefixes are client-side decoration."""

    __tablename__ = "message"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Nullable: metering self-disables when the DB is unreachable, so there may be no run row.
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("run.id", ondelete="SET NULL"),
        nullable=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)  # user|assistant
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    images: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="complete"
    )  # complete|partial|errored
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Asset(Base):
    """Media a run generated (an Image node's PNG, a TTS node's MP3), recorded so it can be
    listed, searched, counted and deleted.

    Before this table the URL existed only inside the message markdown: nothing could enumerate
    a workspace's generated media, nothing counted its bytes toward the storage figure, and
    nothing could reclaim the object. That is the same gap `Upload` closed for inbound files.

    **`blob_url` is always a real URL.** `store_asset` degrades to an inline `data:` URI when
    blob storage isn't configured, and the node emits no asset event in that case — so a
    multi-MB base64 string never reaches Postgres and `delete_blob` on this column is safe."""

    __tablename__ = "asset"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    # CASCADE: deleting a conversation deletes the media it produced. The confirm dialog names
    # the count so that is not a surprise.
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation.id", ondelete="CASCADE"),
        nullable=True,
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("run.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent.id", ondelete="SET NULL"),
        nullable=True,
    )
    node_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)  # image|audio
    blob_url: Mapped[str] = mapped_column(Text, nullable=False)
    pathname: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    caption: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OrphanBlob(Base):
    """A blob object we failed to delete, parked for the nightly retry.

    Vercel Blob shares no transaction with Postgres, so a delete that spans both can always lose
    one half. `AccountPurge` solves this for a *deleted account*; this is the same idea at row
    granularity, for a live workspace deleting one conversation or one media item. The row is
    written in the same transaction as the database delete, so the pointer to a still-billing
    object is never the thing that goes missing."""

    __tablename__ = "orphan_blob"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspace.id", ondelete="CASCADE"),
        nullable=False,
    )
    blob_url: Mapped[str] = mapped_column(Text, nullable=False)
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


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


class AccountPurge(Base):
    """What still has to be destroyed after an account was deleted, and how far along we are.

    Written by `DELETE /account` and drained by `purge.py` (0017). It exists because the purge
    crosses stores that share no transaction — Vercel Blob and LangGraph's checkpoint tables sit
    outside our own — so *both* inline orderings lose a crash: delete the blobs first and the
    `upload` rows point at nothing; delete the database first and the urls are gone forever while
    the objects keep billing.

    **`account_id` has no foreign key on purpose.** The purge's last step deletes the
    `billing_account` row, and this record has to outlive it as the audit trail. A dangling id
    here is the design.

    There is deliberately **no email column** — see the 0017 docstring.
    """

    __tablename__ = "account_purge"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True, nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # Prefixes rather than expanded thread ids, so the row is the same size for an account with
    # three conversations and one with three hundred thousand.
    thread_prefixes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    # Threads from before `threads.py` namespaced them: no prefix to match, reachable only
    # through `run.thread_id`, so they have to be enumerated.
    legacy_thread_ids: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    # Drained chunk by chunk as deletes succeed, which is what makes a crashed purge resumable
    # instead of re-issuing deletes for objects already gone.
    blob_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    # Chunks Vercel refused. Parked rather than retried forever: a blob failure must never block
    # the database purge, but it must not disappear silently either.
    blob_urls_failed: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    stripe_cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
