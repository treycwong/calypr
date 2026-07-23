"""credit_ledger + cached balance — the grant becomes enforceable

Revision ID: 0014_credit_ledger
Revises: 0013_billing
Create Date: 2026-07-23

`/pricing` advertises 2,000 credits a month and nothing enforced it: credits were computed
(`pricing.credits_for`) but never debited, so a Plus subscriber had no ceiling beyond the
platform-wide kill-switch — which protects the platform, not the plan.

**The ledger is the truth**; `workspace.credit_balance_micro` is a cache updated in the same
transaction, so a run doesn't pay for a `SUM()` over every row a workspace has ever written.
Any disagreement is resolved in the ledger's favour (see `credits.recompute_balance`).

**Micro-credits, as integers.** `credits_for` returns a float on purpose — rounding per node
would round a graph of many cheap nodes to zero on every one of them — so the rounding happens
exactly once, here, at 1 credit = 1,000 micro. Money in floats is how balances drift.

`grant_cycle_anchor` is the date the current month's grant was issued, which makes "have they
been granted this cycle?" a comparison rather than a scan of the ledger.

RLS follows the `run`/`run_usage` pattern: enabled with a `workspace_id` policy, not FORCEd
(the app role owns the table), with app-level filtering as the real boundary.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_credit_ledger"
down_revision: str | None = "0013_billing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace",
        sa.Column(
            "credit_balance_micro", sa.BigInteger(), nullable=False, server_default="0"
        ),
    )
    op.add_column("workspace", sa.Column("grant_cycle_anchor", sa.Date(), nullable=True))

    op.create_table(
        "credit_ledger",
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
        # Signed: + for a grant or top-up, − for a debit. Balance is the sum.
        sa.Column("delta_micro", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),  # grant|debit|topup|adjust
        sa.Column("source", sa.String(), nullable=True),  # run|assist|share|byok
        sa.Column("ref_id", sa.String(), nullable=True),  # run id, invoice id, …
        sa.Column("model", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_credit_ledger_workspace_created", "credit_ledger", ["workspace_id", "created_at"]
    )
    # A grant is issued once per workspace per cycle; the unique index is what makes a
    # redelivered `invoice.paid` a no-op rather than free credits.
    op.create_index(
        "uq_credit_ledger_grant_ref",
        "credit_ledger",
        ["workspace_id", "ref_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'grant'"),
    )

    op.execute("ALTER TABLE credit_ledger ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY credit_ledger_tenant_isolation ON credit_ledger
        USING (workspace_id = current_setting('calypr.workspace_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS credit_ledger_tenant_isolation ON credit_ledger")
    op.drop_index("uq_credit_ledger_grant_ref", table_name="credit_ledger")
    op.drop_index("ix_credit_ledger_workspace_created", table_name="credit_ledger")
    op.drop_table("credit_ledger")
    op.drop_column("workspace", "grant_cycle_anchor")
    op.drop_column("workspace", "credit_balance_micro")
