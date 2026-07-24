"""Set a workspace's plan and credit balance — a **testing** tool for local databases.

Exists because exercising the paid tiers by hand otherwise means either paying Stripe or writing
UPDATEs by hand, and a hand-written UPDATE moves `workspace.credit_balance_micro` without a
`credit_ledger` row, which is exactly the drift the ledger exists to make impossible.

So this writes a real `kind='adjust'` ledger row through `credits._write`: the balance and its
audit trail move together, `recompute_balance` still reconciles, and the adjustment is visible
next to the grants and debits rather than being an unexplained jump.

    # look first — no flags, no writes
    uv run python scripts/set_credits.py --workspace <uuid>

    # then act
    uv run python scripts/set_credits.py --workspace <uuid> --plan plus --credits 2000 --yes

Guardrails, because this moves money-shaped numbers:

- **Nothing is written without `--yes`.** The default run prints the current state and the change
  it *would* make.
- **It refuses a non-local database unless `--i-know-this-is-not-local` is also passed.** The
  connection string comes from `CALYPR_DATABASE_URL`, and `railway run` injects production's —
  so the difference between resetting your laptop and editing a paying customer's balance is one
  shell prefix. Adjusting real balances is a support decision, not a scripting one.
"""

from __future__ import annotations

import argparse
import sys

from calypr_api import credits, entitlements
from calypr_api.config import settings
from calypr_api.db.models import Workspace
from calypr_api.db.session import SessionLocal

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def _is_local(url: str) -> bool:
    host = url.rsplit("@", 1)[-1] if "@" in url else url
    return any(h in host for h in LOCAL_HOSTS)


def _show(session, workspace: Workspace) -> None:
    balance = credits.balance_micro(session, workspace.id)
    print(f"  plan               {workspace.plan!r}")
    print(f"  credit_balance     {balance / credits.MICRO:,.3f} credits ({balance:,} micro)")
    print(f"  grant_cycle_anchor {workspace.grant_cycle_anchor}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, help="workspace id (uuid)")
    parser.add_argument("--plan", choices=entitlements.PLANS, help="set the entitlement tier")
    parser.add_argument(
        "--credits", type=float, help="set the balance to exactly this many credits"
    )
    parser.add_argument("--yes", action="store_true", help="actually write the change")
    parser.add_argument(
        "--i-know-this-is-not-local",
        action="store_true",
        help="permit writing to a non-local database (you almost certainly do not want this)",
    )
    args = parser.parse_args()

    url = settings.database_url
    host = url.rsplit("@", 1)[-1] if "@" in url else url
    local = _is_local(url)
    print(f"DB {host}{'' if local else '   ** NOT LOCAL **'}\n")

    if not local and not args.i_know_this_is_not_local:
        sys.exit(
            "refusing to touch a non-local database.\n"
            "If you genuinely mean to, pass --i-know-this-is-not-local — but a real balance is a\n"
            "support decision, and the ledger is the record of it."
        )

    with SessionLocal() as session:
        workspace = session.get(Workspace, args.workspace)
        if workspace is None:
            sys.exit(f"no workspace with id {args.workspace!r}")

        print(f"workspace {workspace.id} ({workspace.name!r})\nbefore:")
        _show(session, workspace)

        plan = args.plan or workspace.plan
        changes: list[str] = []
        if args.plan and args.plan != workspace.plan:
            changes.append(f"plan {workspace.plan!r} → {args.plan!r}")
        delta = 0
        if args.credits is not None:
            target = credits.to_micro(args.credits)
            delta = target - credits.balance_micro(session, workspace.id)
            changes.append(f"balance → {args.credits:,.3f} credits (adjust {delta:+,} micro)")

        if not changes:
            print("\nnothing to change (pass --plan and/or --credits)")
            return

        print("\nwould change:")
        for c in changes:
            print(f"  {c}")

        if not args.yes:
            print("\ndry run — pass --yes to apply")
            return

        if args.plan:
            workspace.plan = args.plan
        if args.credits is not None and delta:
            credits._write(
                session,
                workspace.id,
                delta,
                "adjust",
                source="admin",
                ref_id=f"set_credits:{plan}",
            )
        if args.credits is not None:
            # Anchor this cycle so `ensure_current_grant` doesn't immediately top the balance
            # back up to the plan allowance and silently undo what was just set.
            workspace.grant_cycle_anchor = credits.date.today()
        session.commit()

        session.refresh(workspace)
        print("\nafter:")
        _show(session, workspace)


if __name__ == "__main__":
    main()
