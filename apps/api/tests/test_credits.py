"""The credit ledger: rounding, grant idempotency, and what a debit is allowed to do.

These are money-correctness tests. The properties that matter are the ones where being wrong
costs somebody something: rounding that leaks free usage, a redelivered webhook granting twice,
a concurrent debit lost to read-modify-write.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from calypr_api import credits, entitlements
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import CreditLedger, Workspace
from calypr_api.db.session import SessionLocal, engine
from sqlalchemy import text


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


@pytest.fixture
def workspace():
    """A throwaway workspace, removed afterwards (ledger rows cascade)."""
    with SessionLocal() as s:
        ws = Workspace(name=f"credits-test-{uuid.uuid4().hex[:8]}", plan=entitlements.PLUS)
        s.add(ws)
        s.commit()
        s.refresh(ws)
        wid = ws.id
    yield wid
    with SessionLocal() as s:
        s.query(Workspace).filter(Workspace.id == wid).delete()
        s.commit()


# --- rounding (pure) ---------------------------------------------------------------------------


def test_a_credit_is_a_thousand_micro():
    assert credits.to_micro(1.0) == 1_000
    assert credits.to_micro(2_000) == 2_000_000


def test_fractional_credits_round_up_not_down():
    """Up, deliberately. A debit that rounds *down* is free usage, and at volume "free" is the
    direction that costs money. The worst over-charge is one micro-credit — a thousandth of a
    cent — which is the right side to err on."""
    assert credits.to_micro(0.0001) == 1
    assert credits.to_micro(1.0001) == 1_001


def test_a_tiny_debit_is_never_rounded_away():
    """The reason `credits_for` returns a float: a graph of many cheap nodes must not round to
    zero on every node. One node's worth of gpt-4o-mini still costs something."""
    from calypr_api.pricing import credits_for

    tiny = credits_for("gpt-4o-mini", 10, 0)
    assert 0 < tiny < 1  # genuinely sub-credit
    assert credits.to_micro(tiny) >= 1


def test_zero_is_zero():
    assert credits.to_micro(0.0) == 0


def test_the_plan_grants_match_the_pricing_spec():
    assert credits.MONTHLY_GRANT[entitlements.PLUS] == 2_000
    assert credits.MONTHLY_GRANT[entitlements.FREE] == 100
    # Beta is a full-product cohort — metering them onto a smaller pool would make their
    # feedback about a product nobody is buying.
    assert credits.MONTHLY_GRANT[entitlements.BETA] == 2_000


# --- granting ----------------------------------------------------------------------------------


@requires_db
def test_a_grant_credits_the_plan_amount(workspace):
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        assert credits.grant_monthly(s, ws, ref_id="in_1") is True
        s.commit()
        assert credits.balance_micro(s, workspace) == 2_000 * credits.MICRO


@requires_db
def test_a_redelivered_invoice_does_not_grant_twice(workspace):
    """Stripe delivers at-least-once, and `invoice.paid` is a grant trigger — so a redelivery
    that granted again would be free money, monthly, forever."""
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_same")
        s.commit()
        assert credits.grant_monthly(s, ws, ref_id="in_same") is False
        s.commit()
        assert credits.balance_micro(s, workspace) == 2_000 * credits.MICRO


@requires_db
def test_a_second_grant_in_the_same_month_is_refused(workspace):
    """Belt and braces on top of `ref_id`: a *different* invoice inside the same cycle (a plan
    change, a proration) must not stack a second month's credits."""
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_1", cycle=date(2026, 7, 1))
        s.commit()
        assert credits.grant_monthly(s, ws, ref_id="in_2", cycle=date(2026, 7, 20)) is False
        s.commit()
        assert credits.balance_micro(s, workspace) == 2_000 * credits.MICRO


@requires_db
def test_next_month_grants_again(workspace):
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_july", cycle=date(2026, 7, 1))
        s.commit()
        assert credits.grant_monthly(s, ws, ref_id="in_aug", cycle=date(2026, 8, 1)) is True
        s.commit()
        assert credits.balance_micro(s, workspace) == 2_000 * credits.MICRO


@requires_db
def test_a_grant_tops_up_to_the_allowance_rather_than_stacking(workspace):
    """"2,000 a month", not "2,000 that pile up". Rollover is explicitly out of v1
    (PRICING-SPEC §1), so an unused balance doesn't compound into a bill we didn't price."""
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_july", cycle=date(2026, 7, 1))
        credits.debit_run(s, workspace, 500, source="run")
        s.commit()
        assert credits.balance_micro(s, workspace) == 1_500 * credits.MICRO

        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_aug", cycle=date(2026, 8, 1))
        s.commit()
        assert credits.balance_micro(s, workspace) == 2_000 * credits.MICRO


@requires_db
def test_a_free_workspace_gets_the_smaller_grant(workspace):
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        ws.plan = entitlements.FREE
        credits.grant_monthly(s, ws, ref_id="free_cycle")
        s.commit()
        assert credits.balance_micro(s, workspace) == 100 * credits.MICRO


# --- debiting ----------------------------------------------------------------------------------


@requires_db
def test_a_debit_reduces_the_balance_and_leaves_a_trail(workspace):
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_1")
        credits.debit_run(s, workspace, 16.0, source="run", ref_id="run_1", model="gpt-image-2")
        s.commit()
        assert credits.balance_micro(s, workspace) == (2_000 - 16) * credits.MICRO
        rows = s.query(CreditLedger).filter(CreditLedger.workspace_id == workspace).all()
        # The history is what makes "why is my balance this?" answerable when someone disputes it.
        assert {r.kind for r in rows} == {"grant", "debit"}
        debit = next(r for r in rows if r.kind == "debit")
        assert debit.model == "gpt-image-2" and debit.ref_id == "run_1"


@requires_db
def test_a_run_already_in_flight_may_go_negative(workspace):
    """Debits happen *after* the run. A run that started with credit and overshot finishes
    rather than being killed mid-answer — `max_tokens` bounds the overshoot. The *next* call is
    what gets refused."""
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_1")
        credits.debit_run(s, workspace, 2_500, source="run")
        s.commit()
        assert credits.balance_micro(s, workspace) < 0
        assert credits.has_credits(s, workspace) is False


@requires_db
def test_a_zero_cost_debit_writes_nothing(workspace):
    """BYOK and the `fake` model cost us nothing, so they must not litter the ledger with
    zero rows — the trail should only contain movements."""
    with SessionLocal() as s:
        assert credits.debit_run(s, workspace, 0.0, source="byok") == 0
        s.commit()
        assert s.query(CreditLedger).filter(CreditLedger.workspace_id == workspace).count() == 0


@requires_db
def test_a_debit_from_a_stale_read_does_not_lose_the_other_one(workspace):
    """The lost-update scenario. The cache moves with a SQL expression
    (`credit_balance_micro + delta`), not read-modify-write, so a session holding a *stale*
    balance still applies a correct relative change instead of stamping its own arithmetic over
    someone else's debit.

    Written sequentially with a stale read in the middle rather than as two open transactions:
    two sessions updating the same row without committing simply deadlock on the row lock,
    which tests the database's locking rather than this code."""
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_1")
        s.commit()

    stale = SessionLocal()
    stale_balance = credits.balance_micro(stale, workspace)  # read before the other debit

    with SessionLocal() as other:
        credits.debit_run(other, workspace, 10, source="run")
        other.commit()

    # `stale` still believes the pre-debit balance...
    assert stale_balance == 2_000 * credits.MICRO
    credits.debit_run(stale, workspace, 10, source="run")
    stale.commit()
    stale.close()

    # ...and both debits survive, because neither wrote an absolute figure.
    with SessionLocal() as s:
        assert credits.balance_micro(s, workspace) == (2_000 - 20) * credits.MICRO


# --- the cache is only a cache -----------------------------------------------------------------


@requires_db
def test_the_ledger_wins_when_the_cache_drifts(workspace):
    """The cache exists for speed; the ledger is the truth. A crash between the two writes must
    be repairable without arithmetic by hand."""
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_1")
        s.commit()
        # Corrupt the cache behind the ledger's back.
        s.query(Workspace).filter(Workspace.id == workspace).update({"credit_balance_micro": 42})
        s.commit()
        assert credits.balance_micro(s, workspace) == 42

        assert credits.recompute_balance(s, workspace) == 2_000 * credits.MICRO
        s.commit()
        assert credits.balance_micro(s, workspace) == 2_000 * credits.MICRO


@requires_db
def test_has_credits_is_false_at_exactly_zero(workspace):
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_1")
        credits.debit_run(s, workspace, 2_000, source="run")
        s.commit()
        assert credits.balance_micro(s, workspace) == 0
        assert credits.has_credits(s, workspace) is False


# --- the enforcement gate ------------------------------------------------------------------


def test_enforcement_is_off_without_an_internal_key(monkeypatch, workspace):
    """Same dev/CI carve-out as `require_code_export`: local dev, CI and the e2e suite all
    resolve to the shared dev workspace, so metering them would break start.sh's promise and
    the test suite while protecting nothing."""
    monkeypatch.setattr(settings, "internal_key", "")
    assert credits.check_can_run(workspace) is None


@requires_db
def test_anonymous_traffic_is_never_credit_limited(monkeypatch):
    """The logged-out playground and share-link runs are deliberately not tenant-scoped, so in
    production they fall back to the *shared* dev workspace. Metering that would mean the first
    anonymous visitor to exhaust it breaks the playground for everyone — a far worse failure
    than the spend it prevents. `CALYPR_PLATFORM_SPEND_CAP_USD` is the control for that traffic.
    """
    monkeypatch.setattr(settings, "internal_key", "prod-key")
    dev = uuid.UUID(DEV_WORKSPACE_ID)
    with SessionLocal() as s:
        # Even deeply overdrawn, it must not be refused.
        s.query(Workspace).filter(Workspace.id == dev).update({"credit_balance_micro": -999_000})
        s.commit()
    try:
        assert credits.check_can_run(dev) is None
    finally:
        with SessionLocal() as s:
            s.query(Workspace).filter(Workspace.id == dev).update({"credit_balance_micro": 0})
            s.commit()


@requires_db
def test_a_workspace_that_was_never_granted_gets_its_allowance_on_first_use(
    monkeypatch, workspace
):
    """Every workspace that existed before the ledger shipped has a zero balance and no anchor.
    Without a lazy grant, enforcement would refuse all of them — people who never received the
    credits they're entitled to, told they're out of credits."""
    monkeypatch.setattr(settings, "internal_key", "prod-key")
    with SessionLocal() as s:
        assert credits.balance_micro(s, workspace) == 0

    assert credits.check_can_run(workspace) is None  # granted, then allowed

    with SessionLocal() as s:
        assert credits.balance_micro(s, workspace) == 2_000 * credits.MICRO


@requires_db
def test_an_exhausted_workspace_is_refused_with_actionable_copy(monkeypatch, workspace):
    monkeypatch.setattr(settings, "internal_key", "prod-key")
    with SessionLocal() as s:
        ws = s.get(Workspace, workspace)
        credits.grant_monthly(s, ws, ref_id="in_1")
        credits.debit_run(s, workspace, 2_000, source="run")
        s.commit()

    message = credits.check_can_run(workspace)
    assert message is not None
    # Says what to do, not just what went wrong — someone blocked mid-work needs a way forward.
    assert "API key" in message or "reset" in message


@requires_db
def test_the_check_fails_open_when_the_database_is_unreachable(monkeypatch, workspace):
    """A DB hiccup must not stop paying customers working. The exposure is one run; the platform
    spend cap is the backstop for the pathological case."""
    monkeypatch.setattr(settings, "internal_key", "prod-key")
    monkeypatch.setattr(
        credits, "SessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("db down"))
    )
    assert credits.check_can_run(workspace) is None
