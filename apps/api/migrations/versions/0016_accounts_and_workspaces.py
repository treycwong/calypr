"""accounts: billing moves off the workspace so a user can have several

Revision ID: 0016_accounts_and_workspaces
Revises: 0015_subscription_cycle
Create Date: 2026-08-02

Until now a user *was* a workspace: `workspace.owner_user_id` carried a unique constraint and
`resolve_workspace(user_id)` found-or-created exactly one. Plus buys three, which breaks that
in one specific way — **plan, Stripe, and credits all live on the workspace row**, so three
workspaces would mean three subscriptions and 3× the monthly grant.

So the tenant splits in two. An **account** is who pays (plan, Stripe customer, credit balance,
storage); a **workspace** is where work lives (name, model defaults, agents, runs). Quotas —
projects, credits, storage — pool at the account. The RLS GUC stays *workspace*-shaped, which is
what keeps this migration small: every domain table's policy is untouched, and only the two
account-scoped tables (`billing_account`, `credit_ledger`) get a new predicate that reaches up
through `workspace.account_id`.

**The table is `billing_account`, not `account`, and it has to stay that way.** Better Auth owns
`user`, `session`, `account` and `verification` in this same database — it manages them itself,
outside Alembic, so they are invisible to `alembic upgrade` and to any local database that has
never run the web app's auth. `account` is Better Auth's OAuth-link table (`providerId`,
`accessToken`, `refreshToken`, `password`). Creating our own `account` alongside it fails the
deploy at `preDeployCommand` — and would be far worse if it somehow didn't. **Never name a table
`user`, `session`, `account` or `verification` here.**

**Account ids are reused from workspace ids, deliberately.** It makes the backfill correlation-
free (no lookup table, no ordering), and — the reason that actually matters — Stripe checkout
sessions in flight at deploy time carry `client_reference_id = <workspace id>`. Because the
account inherits that id, those sessions resolve to the right account when they complete. Do not
switch to fresh uuids without first draining checkout sessions.

`credit_ledger.workspace_id` survives as **provenance**, not as the balance key: it records which
workspace spent a credit, which is what makes a future per-workspace usage breakdown possible
while the balance itself stays account-wide.

`upload` is new and starts empty. Vercel Blob objects have never had a DB row, so there is no
backfill to do and pre-existing blobs stay unaccounted for — this begins the record from here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_accounts_and_workspaces"
down_revision: str | None = "0015_subscription_cycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The shared dev/anonymous workspace (calypr_api.constants.DEV_WORKSPACE_ID). Its account is
# seeded explicitly so a fresh database is consistent even before anyone signs in.
DEV_WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"

# Reaches from the request's workspace GUC up to the account that owns it. Used by both
# account-scoped policies.
_ACCOUNT_OF_CURRENT_WORKSPACE = """
    (SELECT w.account_id FROM workspace w
      WHERE w.id = current_setting('calypr.workspace_id', true)::uuid)
"""


def upgrade() -> None:
    # --- account ---------------------------------------------------------------------------
    op.create_table(
        "billing_account",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # = Better Auth user.id. No FK, for the same reason 0003 declined one: the `user` table
        # is managed by Better Auth, not Alembic, and coupling the two migration tools is worse
        # than an orphan row. NULL for the dev account (UNIQUE permits repeated NULLs).
        sa.Column("owner_user_id", sa.String(), nullable=True, unique=True),
        sa.Column("plan", sa.String(), nullable=False, server_default=sa.text("'free'")),
        sa.Column("stripe_customer_id", sa.String(), nullable=True, unique=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "credit_balance_micro", sa.BigInteger(), nullable=False, server_default="0"
        ),
        sa.Column("grant_cycle_anchor", sa.Date(), nullable=True),
        # Written by the nightly measurement job (`storage_usage.py`), not on the hot path.
        # NULL `storage_measured_at` means "never measured" — the UI says so rather than
        # claiming a confident 0 B.
        sa.Column("storage_bytes", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("storage_measured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    # One account per existing workspace, **keeping the id** (see the module docstring).
    op.execute(
        """
        INSERT INTO billing_account (id, owner_user_id, plan, stripe_customer_id,
                             stripe_subscription_id, current_period_end, cancel_at_period_end,
                             credit_balance_micro, grant_cycle_anchor, created_at)
        SELECT id, owner_user_id, plan, stripe_customer_id,
               stripe_subscription_id, current_period_end, cancel_at_period_end,
               credit_balance_micro, grant_cycle_anchor, created_at
          FROM workspace
        """
    )

    # --- workspace: link up, shed everything that is now the account's ------------------------
    op.add_column(
        "workspace", sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.execute("UPDATE workspace SET account_id = id")
    op.alter_column("workspace", "account_id", nullable=False)
    op.create_foreign_key(
        "workspace_account_id_fkey", "workspace", "billing_account",
        ["account_id"], ["id"],
        ondelete="CASCADE",
    )
    # The switcher lists a user's workspaces oldest-first; the default workspace is the first row.
    op.create_index("ix_workspace_account_created", "workspace", ["account_id", "created_at"])

    op.drop_constraint("workspace_owner_user_id_key", "workspace", type_="unique")
    op.drop_constraint("uq_workspace_stripe_customer_id", "workspace", type_="unique")
    for column in (
        "owner_user_id",
        "plan",
        "stripe_customer_id",
        "stripe_subscription_id",
        "current_period_end",
        "cancel_at_period_end",
        "credit_balance_micro",
        "grant_cycle_anchor",
    ):
        op.drop_column("workspace", column)

    # --- credit_ledger: balance keys to the account, workspace_id becomes provenance ----------
    op.add_column(
        "credit_ledger", sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.execute(
        """
        UPDATE credit_ledger cl SET account_id = w.account_id
          FROM workspace w WHERE w.id = cl.workspace_id
        """
    )
    # No NULLs are possible: workspace_id was NOT NULL with an ON DELETE CASCADE FK, so every
    # ledger row still has its workspace, and every workspace now has an account.
    op.alter_column("credit_ledger", "account_id", nullable=False)
    op.create_foreign_key(
        "credit_ledger_account_id_fkey", "credit_ledger", "billing_account",
        ["account_id"], ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("credit_ledger", "workspace_id", nullable=True)

    # The grant is issued once per *account* per cycle now. Dropping and recreating inside the
    # migration's transaction means there is no window where a redelivered `invoice.paid` could
    # slip past both indexes.
    op.drop_index("uq_credit_ledger_grant_ref", table_name="credit_ledger")
    op.create_index(
        "uq_credit_ledger_grant_ref",
        "credit_ledger",
        ["account_id", "ref_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'grant'"),
    )
    op.create_index(
        "ix_credit_ledger_account_created", "credit_ledger", ["account_id", "created_at"]
    )
    # ix_credit_ledger_workspace_created stays — it's what the per-workspace breakdown will read.

    op.execute("DROP POLICY IF EXISTS credit_ledger_tenant_isolation ON credit_ledger")
    op.execute(
        f"""
        CREATE POLICY credit_ledger_tenant_isolation ON credit_ledger
        USING (account_id = {_ACCOUNT_OF_CURRENT_WORKSPACE})
        """
    )

    # --- account RLS --------------------------------------------------------------------------
    op.execute("ALTER TABLE billing_account ENABLE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY account_tenant_isolation ON billing_account
        USING (id = {_ACCOUNT_OF_CURRENT_WORKSPACE})
        """
    )

    # --- upload: so blob bytes are attributable at all ------------------------------------------
    op.create_table(
        "upload",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("blob_url", sa.String(), nullable=False),
        sa.Column("pathname", sa.String(), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_upload_workspace_created", "upload", ["workspace_id", "created_at"])
    op.execute("ALTER TABLE upload ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY upload_tenant_isolation ON upload
        USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)
        """
    )

    # --- resolvers ------------------------------------------------------------------------------
    # Find-or-create the account, and guarantee it owns at least one workspace. SECURITY DEFINER
    # so it runs before the per-request tenant GUC is set, same as the 0003 original.
    op.execute(
        """
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
            -- An account with no workspace has nowhere to put work; keep that unrepresentable.
            IF NOT EXISTS (SELECT 1 FROM workspace WHERE account_id = acc) THEN
                INSERT INTO workspace (account_id, name) VALUES (acc, 'Personal');
            END IF;
            RETURN acc;
        END;
        $$;
        """
    )

    # Two-arg: the browser *claims* a workspace (via a cookie the Next proxy forwards) and this
    # validates it against the caller's account. A claim that is absent, malformed, or belongs to
    # someone else all land on the same fallback — the account's first workspace — rather than an
    # error. The cookie is a UI preference, not an authorization token: 403ing on a stale one
    # (after deleting a workspace, or signing in as someone else on a shared machine) would wedge
    # the dashboard with no way back. Rejecting it silently is the safe direction *and* the usable
    # one; `deps.py` logs the rejection so it stays observable.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION resolve_workspace(p_user_id text, p_workspace_id uuid)
        RETURNS uuid
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
        DECLARE acc uuid; ws uuid;
        BEGIN
            acc := resolve_account(p_user_id);
            IF p_workspace_id IS NOT NULL THEN
                SELECT id INTO ws FROM workspace
                 WHERE id = p_workspace_id AND account_id = acc;
                IF ws IS NOT NULL THEN RETURN ws; END IF;
            END IF;
            SELECT id INTO ws FROM workspace
             WHERE account_id = acc ORDER BY created_at, id LIMIT 1;
            RETURN ws;
        END;
        $$;
        """
    )

    # The 0003 one-arg signature keeps working, so any caller missed in this change degrades to
    # the default workspace instead of erroring.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION resolve_workspace(p_user_id text)
        RETURNS uuid
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$ SELECT resolve_workspace(p_user_id, NULL::uuid) $$;
        """
    )

    # The switcher's list. Necessarily SECURITY DEFINER: `workspace`'s RLS policy shows exactly
    # one row under the request GUC, which is precisely the wrong answer here.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION list_account_workspaces(p_user_id text)
        RETURNS TABLE (id uuid, name text, created_at timestamptz)
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
            SELECT w.id, w.name, w.created_at FROM workspace w
             WHERE w.account_id = resolve_account(p_user_id)
             ORDER BY w.created_at, w.id
        $$;
        """
    )

    # --- dev account + the index the storage jobs need -------------------------------------------
    # If the dev workspace exists it already got an account from the backfill; this covers a
    # database where it doesn't yet.
    op.execute(
        f"""
        INSERT INTO billing_account (id) VALUES ('{DEV_WORKSPACE_ID}'::uuid)
        ON CONFLICT (id) DO NOTHING
        """
    )

    # `run.thread_id` is the only link from a workspace to its LangGraph checkpoint rows, so both
    # the storage measurement and the retention GC join on it.
    op.create_index(
        "ix_run_thread_id",
        "run",
        ["thread_id"],
        postgresql_where=sa.text("thread_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_run_thread_id", table_name="run")
    op.execute("DROP FUNCTION IF EXISTS list_account_workspaces(text)")
    op.execute("DROP FUNCTION IF EXISTS resolve_workspace(text, uuid)")
    op.execute("DROP FUNCTION IF EXISTS resolve_account(text)")

    op.execute("DROP POLICY IF EXISTS upload_tenant_isolation ON upload")
    op.drop_index("ix_upload_workspace_created", table_name="upload")
    op.drop_table("upload")

    # credit_ledger back to workspace-keyed
    op.execute("DROP POLICY IF EXISTS credit_ledger_tenant_isolation ON credit_ledger")
    op.execute(
        """
        CREATE POLICY credit_ledger_tenant_isolation ON credit_ledger
        USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)
        """
    )
    op.drop_index("ix_credit_ledger_account_created", table_name="credit_ledger")
    op.drop_index("uq_credit_ledger_grant_ref", table_name="credit_ledger")
    op.create_index(
        "uq_credit_ledger_grant_ref",
        "credit_ledger",
        ["workspace_id", "ref_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'grant'"),
    )
    # Rows written against a workspace that was since deleted can't be restored to NOT NULL;
    # drop them rather than fail the downgrade. (None exist unless a workspace was deleted
    # while on 0016 — the FK cascade used to make that impossible.)
    op.execute("DELETE FROM credit_ledger WHERE workspace_id IS NULL")
    op.alter_column("credit_ledger", "workspace_id", nullable=False)
    op.drop_constraint("credit_ledger_account_id_fkey", "credit_ledger", type_="foreignkey")
    op.drop_column("credit_ledger", "account_id")

    op.execute("DROP POLICY IF EXISTS account_tenant_isolation ON billing_account")

    # Put the billing columns back on workspace and copy the account's values down. A user with
    # several workspaces collapses to their first one — the rest lose their link, which is the
    # unavoidable shape of undoing this.
    op.add_column("workspace", sa.Column("owner_user_id", sa.String(), nullable=True))
    op.add_column(
        "workspace",
        sa.Column("plan", sa.String(), nullable=False, server_default=sa.text("'free'")),
    )
    op.add_column("workspace", sa.Column("stripe_customer_id", sa.String(), nullable=True))
    op.add_column("workspace", sa.Column("stripe_subscription_id", sa.String(), nullable=True))
    op.add_column(
        "workspace", sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "workspace",
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "workspace",
        sa.Column("credit_balance_micro", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column("workspace", sa.Column("grant_cycle_anchor", sa.Date(), nullable=True))

    # Only the account's *first* workspace inherits the billing identity; the others would
    # violate the unique constraints below.
    op.execute(
        """
        UPDATE workspace w SET
            owner_user_id = a.owner_user_id,
            plan = a.plan,
            stripe_customer_id = a.stripe_customer_id,
            stripe_subscription_id = a.stripe_subscription_id,
            current_period_end = a.current_period_end,
            cancel_at_period_end = a.cancel_at_period_end,
            credit_balance_micro = a.credit_balance_micro,
            grant_cycle_anchor = a.grant_cycle_anchor
        FROM billing_account a
        WHERE a.id = w.account_id
          AND w.id = (SELECT w2.id FROM workspace w2
                       WHERE w2.account_id = a.id ORDER BY w2.created_at, w2.id LIMIT 1)
        """
    )
    op.create_unique_constraint("workspace_owner_user_id_key", "workspace", ["owner_user_id"])
    op.create_unique_constraint(
        "uq_workspace_stripe_customer_id", "workspace", ["stripe_customer_id"]
    )

    op.drop_index("ix_workspace_account_created", table_name="workspace")
    op.drop_constraint("workspace_account_id_fkey", "workspace", type_="foreignkey")
    op.drop_column("workspace", "account_id")
    op.drop_table("billing_account")

    # Restore the 0003 one-arg function.
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
