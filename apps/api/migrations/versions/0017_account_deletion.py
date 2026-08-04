"""account deletion: soft-delete, a durable purge record, and a resolver that stops resurrecting

Revision ID: 0017_account_deletion
Revises: 0016_accounts_and_workspaces
Create Date: 2026-08-04

Deleting an account crosses five stores — Stripe, Vercel Blob, LangGraph's checkpoint tables, our
Alembic tables, and Better Auth's — and **there is no transaction that spans them**. This
migration is the part of the answer that lives in the database.

**Why soft-delete plus a background purge, rather than deleting inline.** Both inline orderings
lose a crash. Blobs first, then crash: the `upload` rows now point at objects that are gone.
Database first, then crash: the urls are lost forever, and those objects are simultaneously
unreachable *and still billing*. So the request records what must die (`account_purge`) and marks
the account (`billing_account.deleted_at`); a job does the crossing and can be re-run.

**Why the resolver has to change in the same breath.** `resolve_account` is find-or-create and
`deps.py` commits it on **every** request. Marking an account deleted without this change is a
no-op that silently undoes itself on the next page load — see the guard below.

`account_purge.account_id` is UNIQUE and carries **no foreign key**. That is deliberate: the
purge's final step deletes the `billing_account` row, and this record has to outlive it as the
audit trail. A dangling id here is the point, not an oversight.

There is **no email column**. Storing the email address of someone who asked us to delete their
account would defeat the request. `waitlist` rows are matched and dropped in the request itself,
while we still legitimately hold the address.

**No RLS.** These rows are only ever read by the purge job on an untenanted session, the same way
the GC paths work. A tenant policy here would be a policy that never evaluates.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_account_deletion"
down_revision: str | None = "0016_accounts_and_workspaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: SQLSTATE raised when someone tries to resolve a deleted account. In the user-defined class
#: (`CY`), so it can never collide with a Postgres-assigned code. `deps.py` matches on **this**,
#: never on the message text — see `is_account_deleted`.
DELETED_ACCOUNT_SQLSTATE = "CY001"

# The 0016 definition, restored verbatim by `downgrade()`. Kept as a literal rather than imported
# from the 0016 module so that migration stays immutable history.
_RESOLVE_ACCOUNT_0016 = """
    CREATE OR REPLACE FUNCTION resolve_account(p_user_id text)
    RETURNS uuid
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = pg_catalog, public
    AS $$
    DECLARE acc uuid;
    BEGIN
        INSERT INTO billing_account (owner_user_id) VALUES (p_user_id)
        ON CONFLICT (owner_user_id) DO UPDATE SET owner_user_id = EXCLUDED.owner_user_id
        RETURNING id INTO acc;
        IF NOT EXISTS (SELECT 1 FROM workspace WHERE account_id = acc) THEN
            INSERT INTO workspace (account_id, name) VALUES (acc, 'Personal');
        END IF;
        RETURN acc;
    END;
    $$;
"""


def upgrade() -> None:
    # --- the soft-delete mark ----------------------------------------------------------------
    # Only this one column. Everything about *how far along* the purge is lives in
    # `account_purge`, so there is exactly one source of truth for "is this finished" rather
    # than two that can disagree.
    op.add_column(
        "billing_account",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Partial: the overwhelming majority of accounts are live and should not be in this index.
    # The only queries that use it ask for the deleted ones.
    op.create_index(
        "ix_billing_account_deleted",
        "billing_account",
        ["deleted_at"],
        postgresql_where=sa.text("deleted_at IS NOT NULL"),
    )

    # --- the durable purge record ------------------------------------------------------------
    # Named for the `billing_account` precedent: Better Auth owns `user`, `session`, `account`
    # and `verification` in this same database, outside Alembic. Never name a table any of those.
    op.create_table(
        "account_purge",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # No FK — see the module docstring. UNIQUE so a double-DELETE cannot enqueue twice.
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        # = Better Auth user.id, kept so an operator can correlate during the grace window.
        sa.Column("owner_user_id", sa.String(), nullable=True),
        # **Prefixes, not expanded thread ids.** `ws:<workspace>:` and `share:<token>:` match
        # every conversation they own however many there are, so this row stays small whether
        # the account held three threads or three hundred thousand.
        sa.Column(
            "thread_prefixes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        # Threads predating `threads.py`'s namespacing: no prefix to match, reachable only
        # through `run.thread_id`. Enumerated because there is no other way to name them.
        sa.Column(
            "legacy_thread_ids",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        # Drained as each chunk of deletes succeeds, so a crash resumes instead of re-issuing.
        sa.Column(
            "blob_urls",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        # Chunks Vercel rejected. Parked here rather than retried forever: a blob failure must
        # never block the database purge, but it must also not vanish silently.
        sa.Column(
            "blob_urls_failed",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        # We do **not** delete the Stripe customer — invoices and tax records have to survive.
        # These are kept so the cancellation is auditable after our own row is gone.
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("stripe_cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True),
        # Committed immediately on claim, so a record that reliably kills the worker stops
        # retrying instead of wedging the nightly job forever.
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    # The claim query's index: oldest outstanding request first, live rows only.
    op.create_index(
        "ix_account_purge_pending",
        "account_purge",
        ["requested_at"],
        postgresql_where=sa.text("purged_at IS NULL"),
    )

    # --- stop the resurrection ---------------------------------------------------------------
    # The guard is a predicate on `DO UPDATE`, **inside** the upsert, and it has to stay there.
    # A `SELECT … IF deleted THEN RAISE` in front of the INSERT loses the race against a
    # concurrent soft-delete: the check passes, the delete commits, the insert proceeds. The
    # upsert takes the row lock *before* evaluating its WHERE, so it cannot.
    #
    # When the predicate fails, `DO UPDATE` touches no row and RETURNING yields nothing, so
    # `acc` is NULL.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION resolve_account(p_user_id text)
        RETURNS uuid
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE acc uuid;
        BEGIN
            INSERT INTO billing_account (owner_user_id) VALUES (p_user_id)
            ON CONFLICT (owner_user_id) DO UPDATE SET owner_user_id = EXCLUDED.owner_user_id
                WHERE billing_account.deleted_at IS NULL
            RETURNING id INTO acc;

            IF acc IS NULL THEN
                -- Raise rather than return NULL. Every caller reads a uuid as "proceed", so a
                -- caller who forgot to null-check would fail **open** — serving a deleted
                -- account someone else's workspace, or the shared dev one. An exception cannot
                -- be forgotten.
                RAISE EXCEPTION 'account % is deleted', p_user_id
                    USING ERRCODE = '{DELETED_ACCOUNT_SQLSTATE}';
            END IF;

            -- An account with no workspace has nowhere to put work; keep that unrepresentable.
            IF NOT EXISTS (SELECT 1 FROM workspace WHERE account_id = acc) THEN
                INSERT INTO workspace (account_id, name) VALUES (acc, 'Personal');
            END IF;
            RETURN acc;
        END;
        $$;
        """
    )


def downgrade() -> None:
    """**Do not run this in production once an account has been deleted.**

    Dropping `deleted_at` makes every marked-but-unpurged account live again — the user who asked
    to be deleted can sign in, and their subscription has already been cancelled. Every account
    the purge already finished becomes a broken shell: `account_purge` still names it, but the
    row and its workspaces are gone.

    Safe only on a database where `SELECT count(*) FROM account_purge` is 0.
    """
    op.execute(_RESOLVE_ACCOUNT_0016)
    op.drop_index("ix_account_purge_pending", table_name="account_purge")
    op.drop_table("account_purge")
    op.drop_index("ix_billing_account_deleted", table_name="billing_account")
    op.drop_column("billing_account", "deleted_at")
