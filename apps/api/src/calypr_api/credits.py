"""The credit ledger: granting, debiting, and deciding whether a run may start.

**Credits belong to the account, not the workspace** (0016). The grant is "2,000 a month" for a
person, so it must not multiply when they create a second workspace — every function here keys on
`account_id`, and `credit_ledger.workspace_id` survives only as provenance: which workspace spent
it, for a per-workspace breakdown later.

The ledger is the truth; `account.credit_balance_micro` is a cache kept in the same transaction,
so the hot path reads one column instead of summing every row an account has ever written.
`recompute_balance` resolves any disagreement in the ledger's favour.

**Micro-credits, as integers.** `pricing.credits_for` returns a float deliberately — rounding
per node would round a graph of many cheap nodes to zero on every one of them — so rounding
happens exactly once, here. Money in floats is how balances drift.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from calypr_api import accounts, entitlements
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import Account, CreditLedger
from calypr_api.db.session import SessionLocal

log = logging.getLogger(__name__)

#: Integer micro-credits per credit. The ledger's unit.
MICRO = 1_000

#: Monthly grant per plan (PRICING-SPEC §1), derived from the one capacity table so the number
#: on the pricing page and the number enforced here cannot drift apart. Kept as a module name
#: because it reads better at the call sites than `entitlements.limits(plan).monthly_credits`.
MONTHLY_GRANT = {plan: lim.monthly_credits for plan, lim in entitlements.LIMITS.items()}


def to_micro(credits: float) -> int:
    """Round a credit amount up to whole micro-credits.

    **Up**, not nearest: a debit that rounds down is free usage, and at high volume "free" is
    the direction that costs money. The most a user is ever over-charged is one micro-credit,
    i.e. one thousandth of a cent."""
    micro = credits * MICRO
    return int(micro) if micro == int(micro) else int(micro) + 1


def balance_micro(session: Session, account_id: uuid.UUID) -> int:
    """The cached balance. Cheap — one column, no aggregate."""
    value = session.scalar(
        select(Account.credit_balance_micro).where(Account.id == account_id)
    )
    return int(value or 0)


def recompute_balance(session: Session, account_id: uuid.UUID) -> int:
    """Re-derive the balance from the ledger and correct the cache.

    The ledger wins by definition. Exists so a drifted cache — a crash between the two writes,
    a hand-edited row — is repairable without arithmetic by hand."""
    total = int(
        session.scalar(
            select(func.coalesce(func.sum(CreditLedger.delta_micro), 0)).where(
                CreditLedger.account_id == account_id
            )
        )
        or 0
    )
    session.query(Account).filter(Account.id == account_id).update(
        {"credit_balance_micro": total}
    )
    return total


def _write(
    session: Session,
    account_id: uuid.UUID,
    delta_micro: int,
    kind: str,
    *,
    source: str | None = None,
    ref_id: str | None = None,
    model: str | None = None,
    workspace_id: uuid.UUID | None = None,
) -> None:
    """Append a ledger row and move the cached balance by the same amount, atomically.

    The cache is updated with a SQL expression rather than read-modify-write, so two concurrent
    debits can't both read the same starting balance and lose one of them.

    `workspace_id` is provenance only — where the spend happened. It's absent for grants and
    top-ups, which belong to the account and happen in no particular workspace."""
    session.add(
        CreditLedger(
            account_id=account_id,
            workspace_id=workspace_id,
            delta_micro=delta_micro,
            kind=kind,
            source=source,
            ref_id=ref_id,
            model=model,
        )
    )
    session.query(Account).filter(Account.id == account_id).update(
        {"credit_balance_micro": Account.credit_balance_micro + delta_micro},
        synchronize_session=False,
    )


def grant_monthly(
    session: Session, account: Account, ref_id: str, *, cycle: date | None = None
) -> bool:
    """Issue this cycle's grant. Returns whether anything was granted. Caller commits.

    Idempotent two ways, because both failure modes are real money: `ref_id` is unique per
    account for `kind='grant'` (a redelivered `invoice.paid` can't grant twice), and
    `grant_cycle_anchor` stops a second grant inside the same month even under a different
    `ref_id`.

    Grants **replace** rather than accumulate — the plan is "2,000 a month", not "2,000 that
    pile up forever". Rollover is explicitly out of v1 (`PRICING-SPEC.md` §1)."""
    amount = MONTHLY_GRANT.get(account.plan or entitlements.FREE, 0)
    if amount <= 0:
        return False

    cycle = cycle or date.today()
    anchor = account.grant_cycle_anchor
    if anchor and (anchor.year, anchor.month) == (cycle.year, cycle.month):
        return False  # already granted this cycle

    current = balance_micro(session, account.id)
    target = amount * MICRO
    delta = target - current  # top *up to* the grant, don't stack on leftovers

    savepoint = session.begin_nested()
    try:
        _write(session, account.id, delta, "grant", source="stripe", ref_id=ref_id)
        account.grant_cycle_anchor = cycle
        savepoint.commit()
    except IntegrityError:
        # The unique partial index caught a redelivery for this ref_id.
        savepoint.rollback()
        log.info("grant %s already issued for account %s", ref_id, account.id)
        return False
    return True


def debit_run(
    session: Session,
    account_id: uuid.UUID,
    credits: float,
    *,
    source: str,
    ref_id: str | None = None,
    model: str | None = None,
    workspace_id: uuid.UUID | None = None,
) -> int:
    """Charge a completed run against the account. Returns micro-credits debited. Caller commits.

    Debits **after** the fact, and is allowed to take the balance negative: a run already in
    flight when the balance hits zero finishes rather than being killed mid-answer (`max_tokens`
    bounds the overshoot). The *next* call is what gets refused.

    `workspace_id` records where the run happened; it does not affect the balance."""
    micro = to_micro(credits)
    if micro <= 0:
        return 0
    _write(
        session,
        account_id,
        -micro,
        "debit",
        source=source,
        ref_id=ref_id,
        model=model,
        workspace_id=workspace_id,
    )
    return micro


def has_credits(session: Session, account_id: uuid.UUID) -> bool:
    """Whether a *new* platform-key call may start."""
    return balance_micro(session, account_id) > 0


#: What a caller is told when the balance is spent. `reason` is a stable machine hint (the web
#: app already switches on the same shape from `/parse`'s 402); the message is what a person
#: reads, so it says what to do rather than just what went wrong.
INSUFFICIENT_CREDITS = "credits"


def ensure_current_grant(session: Session, account: Account) -> bool:
    """Issue this cycle's grant lazily, on first use, if it hasn't been issued yet.

    Plus normally gets credited by `invoice.paid`, but that's not the only path that needs to
    work: a Free account has no invoice at all, and every account that existed *before* the
    ledger shipped has a zero balance and no anchor. Without this, enforcement would refuse
    everyone — including people who have never been granted the credits they're entitled to.

    `grant_monthly` is idempotent per cycle, so calling this on every run is a cheap no-op once
    the month's grant exists."""
    return grant_monthly(session, account, ref_id=f"cycle:{date.today():%Y-%m}")


def check_can_run(workspace_id: uuid.UUID | None) -> str | None:
    """Why this workspace's account may not start a platform-key run, or None if it may.

    Takes a *workspace* id because that's what the hot path has, and joins to the account
    internally — credits pool per account, so which of an account's workspaces the run is in
    makes no difference to the answer.

    **Only enforced on a real deployment** (`CALYPR_INTERNAL_KEY` set) — the same carve-out
    `require_code_export` uses. Local dev, CI and the e2e suite all resolve to the shared dev
    workspace, so metering them would break `start.sh`'s promise and the test suite while
    protecting nothing.

    Best-effort and **fails open** otherwise: a DB hiccup must not stop paying customers
    working. The money at risk is bounded by one run, and `CALYPR_PLATFORM_SPEND_CAP_USD` is
    the backstop for the pathological case — whereas failing closed would take the product down
    for everyone on a transient error.
    """
    if workspace_id is None or not settings.internal_key:
        return None
    # The shared dev workspace is where *anonymous* traffic lands in production too (the
    # logged-out playground and share-link runs are deliberately not tenant-scoped). Metering it
    # would mean the first anonymous visitor to exhaust it breaks the playground for everyone,
    # which is a worse failure than the spend it would prevent. `CALYPR_PLATFORM_SPEND_CAP_USD`
    # is the correct control for that traffic, and it already exists.
    if str(workspace_id) == DEV_WORKSPACE_ID:
        return None
    try:
        with SessionLocal() as session:
            account = accounts.account_for_workspace(session, workspace_id)
            if account is None:
                return None
            plan = account.plan or entitlements.FREE
            # Grant first, then check — otherwise someone who has simply never been granted is
            # indistinguishable from someone who has spent their allowance.
            if ensure_current_grant(session, account):
                session.commit()
            # Re-read rather than trusting `account.credit_balance_micro`: `_write` moves the
            # balance with a SQL expression and `synchronize_session=False`, so the in-memory
            # object still holds the pre-grant value.
            if balance_micro(session, account.id) > 0:
                return None
            # Out of credits. Both answers name the two things that actually work from here —
            # wait for the reset, or bring a key — because the reset is a calendar month away
            # and "wait" alone is not an answer to someone mid-task. `grant_monthly` compares
            # (year, month), so "next month" is literally true for both plans; the copy used to
            # promise Plus a reset "on your next billing date", which a mid-month renewal does
            # not deliver.
            if plan == entitlements.FREE:
                return (
                    "You're out of credits for this month. They reset next month — or add your "
                    "own API key in Settings to keep running now, or upgrade to Plus."
                )
            return (
                "You're out of credits for this month. They reset next month — or add your own "
                "API key in Settings to keep running now."
            )
    except Exception:
        log.warning("credit check failed — allowing the run", exc_info=True)
        return None


def usage_summary(session: Session, account: Account) -> dict[str, object]:
    """What the Usage tab shows: how much of this cycle's allowance is left.

    Grants lazily first, so an account that has never run sees its real allowance rather than
    a zero that looks like a bug. Reported in whole credits — micro is a storage detail, and
    "1,983.4 credits" is noise to a person deciding whether they can run something."""
    ensure_current_grant(session, account)
    allowance = MONTHLY_GRANT.get(account.plan or entitlements.FREE, 0)
    remaining_micro = balance_micro(session, account.id)
    # Clamp the display at zero: a negative balance is the bounded overshoot of a run that was
    # already in flight, and "-3 credits" invites a support question with no useful answer.
    remaining = max(0, remaining_micro // MICRO)
    return {
        "allowance": allowance,
        "remaining": remaining,
        "used": max(0, allowance - remaining),
    }
