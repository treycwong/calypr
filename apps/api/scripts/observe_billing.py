"""Read-only observer for the Stripe billing loop — prove `free → plus → free` on a live DB.

Prints, for one workspace, exactly the three things that change across the loop: its `plan`,
its cached `credit_balance_micro` (and the `credit_ledger` rows behind it), and the `stripe_event`
rows Stripe has delivered. Run it before paying, after `plus`, and after cancel — the plan column
is the assertion.

**Read-only.** Only SELECTs; it never writes. Point it at prod by exporting the prod connection
string first (a *direct* Neon endpoint is fine — this opens one short-lived connection):

    CALYPR_DATABASE_URL='postgresql+psycopg://…' \
        uv run python scripts/observe_billing.py --customer cus_Uw5V71aLHnaox9

Selectors (pick one; default lists candidates):
    --customer cus_…    the Stripe customer id from the dashboard
    --workspace <uuid>  the workspace id directly
    (none)              lists every workspace that is not plain `free` or has a customer id,
                        plus the most recent stripe_event rows — use it to find the right id

Note on RLS: `workspace` and `credit_ledger` carry row-level security. Connect with the role that
owns the tables (the same credential the API uses) so rows are visible; a restricted role scoped by
`calypr.workspace_id` would hide everything this script is trying to show.
"""

from __future__ import annotations

import argparse

from sqlalchemy import desc, or_, select

from calypr_api.config import settings
from calypr_api.db.models import CreditLedger, StripeEvent, Workspace
from calypr_api.db.session import SessionLocal

MICRO = 1_000  # micro-credits per credit; mirrors calypr_api.credits.MICRO


def _fmt_credits(micro: int) -> str:
    return f"{micro / MICRO:,.3f} credits ({micro:,} micro)"


def _print_workspace(session, workspace: Workspace) -> None:
    print("workspace")
    print(f"  id                 {workspace.id}")
    print(f"  name               {workspace.name}")
    print(f"  plan               {workspace.plan!r}")
    print(f"  stripe_customer_id {workspace.stripe_customer_id}")
    print(f"  credit_balance     {_fmt_credits(workspace.credit_balance_micro)}")
    print(f"  grant_cycle_anchor {workspace.grant_cycle_anchor}")

    rows = session.scalars(
        select(CreditLedger)
        .where(CreditLedger.workspace_id == workspace.id)
        .order_by(desc(CreditLedger.created_at))
        .limit(10)
    ).all()
    print(f"\ncredit_ledger (last {len(rows)})")
    if not rows:
        print("  (none)")
    for r in rows:
        print(
            f"  {r.created_at:%Y-%m-%d %H:%M:%S}  {r.kind:<6} "
            f"{_fmt_credits(r.delta_micro):<28} source={r.source} ref={r.ref_id}"
        )


def _print_recent_events(session, limit: int = 15) -> None:
    rows = session.scalars(
        select(StripeEvent).order_by(desc(StripeEvent.received_at)).limit(limit)
    ).all()
    print(f"\nstripe_event (last {len(rows)}, newest first)")
    if not rows:
        print("  (none)")
    for r in rows:
        print(f"  {r.received_at:%Y-%m-%d %H:%M:%S}  {r.type:<38} {r.id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customer", help="Stripe customer id (cus_…)")
    parser.add_argument("--workspace", help="workspace id (uuid)")
    args = parser.parse_args()

    # Show which DB we're pointed at (host only — never the password).
    url = settings.database_url
    print(f"DB {url.rsplit('@', 1)[-1] if '@' in url else url}\n")

    with SessionLocal() as session:
        workspace: Workspace | None = None
        if args.customer:
            workspace = session.scalar(
                select(Workspace).where(Workspace.stripe_customer_id == args.customer)
            )
            if workspace is None:
                print(f"no workspace maps to customer {args.customer!r} yet")
        elif args.workspace:
            workspace = session.get(Workspace, args.workspace)
            if workspace is None:
                print(f"no workspace with id {args.workspace!r}")

        if workspace is not None:
            _print_workspace(session, workspace)
        elif not (args.customer or args.workspace):
            candidates = session.scalars(
                select(Workspace)
                .where(or_(Workspace.plan != "free", Workspace.stripe_customer_id.isnot(None)))
                .order_by(desc(Workspace.created_at))
            ).all()
            print(f"candidate workspaces (not plain free, or has a customer id) — {len(candidates)}")
            if not candidates:
                print("  (none — everyone is plain free with no Stripe customer)")
            for w in candidates:
                print(
                    f"  {w.id}  plan={w.plan:<5} "
                    f"customer={w.stripe_customer_id}  bal={_fmt_credits(w.credit_balance_micro)}"
                )

        _print_recent_events(session)


if __name__ == "__main__":
    main()
