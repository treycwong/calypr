"""What a lapsed subscription is allowed to take back.

Cancelling doesn't downgrade immediately — Stripe sets `cancel_at_period_end`, the subscription
stays `active`, and `plan_for_status` keeps the account on Plus until the period actually ends.
That part was already right. These tests cover the moment *after*, which wasn't.

The governing rule: **a downgrade takes back capacity, never data.** Capacity is recoverable by
re-subscribing; run state deleted by last night's GC is not. So the two things asserted hardest
here are that nothing is destroyed inside the grace window, and that credits already granted are
never clawed back.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from calypr_api import billing, credits, entitlements, storage_usage
from calypr_api.db.models import Account, CreditLedger, Run
from calypr_api.db.session import SessionLocal, engine
from sqlalchemy import text

pytestmark = []


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


def _write_checkpoint(session, thread_id: str) -> None:
    """Fake a LangGraph checkpoint — those tables belong to `AsyncPostgresSaver`, not Alembic."""
    session.execute(
        text(
            "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, type,"
            " checkpoint, metadata) VALUES (:t, '', :c, 'test', '{}'::jsonb, '{}'::jsonb)"
        ),
        {"t": thread_id, "c": str(uuid.uuid4())},
    )
    session.execute(
        text(
            "INSERT INTO checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type,"
            " blob) VALUES (:t, '', 'messages', '1', 'test', :b)"
        ),
        {"t": thread_id, "b": b"x" * 64},
    )


def _aged_thread(session, workspace_id: uuid.UUID, days: int) -> str:
    """A run + checkpoint `days` old."""
    thread = f"dg-{uuid.uuid4().hex}"
    session.add(
        Run(workspace_id=workspace_id, thread_id=thread, status="completed", source="playground")
    )
    session.flush()
    session.execute(
        text("UPDATE run SET created_at = now() - make_interval(days => :d) WHERE thread_id = :t"),
        {"d": days, "t": thread},
    )
    _write_checkpoint(session, thread)
    return thread


def _survives(thread: str) -> bool:
    with SessionLocal() as s:
        return (
            s.execute(
                text("SELECT count(*) FROM checkpoints WHERE thread_id = :t"), {"t": thread}
            ).scalar()
            > 0
        )


def _downgrade(account_id: uuid.UUID, *, changed_days_ago: float) -> None:
    """Put an account on Free with its plan change stamped `changed_days_ago` in the past."""
    with SessionLocal() as s:
        s.execute(
            text(
                "UPDATE billing_account SET plan = 'free',"
                " plan_changed_at = now() - make_interval(secs => :secs) WHERE id = :a"
            ),
            {"secs": changed_days_ago * 86_400, "a": str(account_id)},
        )
        s.commit()


# --- the headline: a downgrade destroys nothing ---------------------------------------------------


@requires_db
def test_a_fresh_downgrade_collects_nothing(tenant_factory):
    """**The test this whole change exists for.**

    Retention is evaluated at collection time, so before the grace window a lapsed subscription
    made every thread between the paid TTL (30d) and the free one (7d) expired *the instant it
    lapsed* — and that night's GC deleted it. Silent, irreversible, triggered by a billing event
    the user may not have noticed completing."""
    tenant = tenant_factory(entitlements.PLUS)
    with SessionLocal() as s:
        ten_days = _aged_thread(s, tenant.workspace_id, 10)
        forty_days = _aged_thread(s, tenant.workspace_id, 40)
        s.commit()

    _downgrade(tenant.account_id, changed_days_ago=0)

    with SessionLocal() as s:
        storage_usage.gc_checkpoints(s)

    assert _survives(ten_days), "a fresh downgrade must not collect state the paid plan retained"
    # The control: the grace window is *not* a suspension of the GC. Something past even the
    # most generous retention still goes, or this "fix" would just be an off switch.
    assert not _survives(forty_days)


@requires_db
def test_the_grace_window_expires(tenant_factory):
    """It's a window, not an amnesty — once it closes, Free retention applies as normal."""
    tenant = tenant_factory(entitlements.PLUS)
    with SessionLocal() as s:
        thread = _aged_thread(s, tenant.workspace_id, 10)
        s.commit()

    _downgrade(tenant.account_id, changed_days_ago=entitlements.DOWNGRADE_GRACE_DAYS + 1)

    with SessionLocal() as s:
        storage_usage.gc_checkpoints(s)

    assert not _survives(thread)


@requires_db
def test_a_long_settled_free_account_is_unaffected(tenant_factory):
    """`plan_changed_at IS NULL` — every account that existed before 0018 — keeps the old
    behaviour exactly. The migration deliberately backfills nothing."""
    tenant = tenant_factory(entitlements.FREE)
    with SessionLocal() as s:
        thread = _aged_thread(s, tenant.workspace_id, 10)
        s.commit()
        assert s.get(Account, tenant.account_id).plan_changed_at is None

    with SessionLocal() as s:
        storage_usage.gc_checkpoints(s)

    assert not _survives(thread)


@requires_db
def test_the_sql_and_the_python_agree(tenant_factory):
    """`retention_days` and the GC's CASE are the same rule written twice, in two languages. If
    they drift, the drift is invisible — one of them decides what the UI could promise and the
    other decides what actually gets deleted."""
    just_now = datetime.now(UTC)
    stale = just_now - timedelta(days=entitlements.DOWNGRADE_GRACE_DAYS + 1)

    assert entitlements.retention_days(entitlements.FREE, None) == 7
    assert entitlements.retention_days(entitlements.PLUS, None) == 30
    assert entitlements.retention_days(entitlements.FREE, just_now) == 30  # graced
    assert entitlements.retention_days(entitlements.FREE, stale) == 7  # window closed

    # And the collector agrees for the graced case.
    tenant = tenant_factory(entitlements.PLUS)
    with SessionLocal() as s:
        thread = _aged_thread(s, tenant.workspace_id, 20)
        s.commit()
    _downgrade(tenant.account_id, changed_days_ago=1)
    with SessionLocal() as s:
        storage_usage.gc_checkpoints(s)
    assert _survives(thread)


# --- plan_changed_at is only stamped on a real change ---------------------------------------------


def test_set_plan_stamps_only_a_real_change():
    """A redelivered webhook, or a `cancel_at_period_end` flip (which arrives as an update with
    the *same* entitling status), must not re-open the grace window. Otherwise retention could be
    extended indefinitely by events the user never caused."""
    account = Account(plan=entitlements.FREE)

    assert billing.set_plan(account, entitlements.PLUS) is True
    stamped = account.plan_changed_at
    assert stamped is not None

    # Same plan again: no change, no re-stamp.
    assert billing.set_plan(account, entitlements.PLUS) is False
    assert account.plan_changed_at == stamped


def test_a_beta_account_is_not_downgraded_or_stamped():
    """`beta` is granted by hand and has no subscription, so a stray `subscription.deleted` for a
    customer that somehow maps to them must take nothing away — including their retention."""
    account = Account(plan=entitlements.BETA)
    assert billing.set_plan(account, entitlements.FREE) is False
    assert account.plan_changed_at is None


# --- credits are never clawed back ----------------------------------------------------------------


@requires_db
def test_a_downgrade_does_not_take_back_granted_credits(tenant_factory):
    """The balance is smaller than a Plus grant but larger than a Free one. Topping "down" would
    write a **negative row labelled `grant`** and take back credits already given."""
    tenant = tenant_factory(entitlements.PLUS)
    with SessionLocal() as s:
        account = s.get(Account, tenant.account_id)
        credits.grant_monthly(s, account, ref_id=f"test:{uuid.uuid4().hex}")
        s.commit()
        before = credits.balance_micro(s, tenant.account_id)
    assert before == entitlements.limits(entitlements.PLUS).monthly_credits * credits.MICRO

    # Downgrade, then let the *next* cycle's grant run.
    _downgrade(tenant.account_id, changed_days_ago=0)
    with SessionLocal() as s:
        account = s.get(Account, tenant.account_id)
        account.grant_cycle_anchor = None  # pretend a new month arrived
        s.commit()
        credits.grant_monthly(s, account, ref_id=f"test:{uuid.uuid4().hex}")
        s.commit()
        after = credits.balance_micro(s, tenant.account_id)
        negatives = (
            s.query(CreditLedger)
            .filter(CreditLedger.account_id == tenant.account_id, CreditLedger.kind == "grant")
            .filter(CreditLedger.delta_micro < 0)
            .count()
        )

    assert negatives == 0, "a downgrade must never write a negative grant"
    assert after == before, "the balance already granted survives the downgrade"


@requires_db
def test_a_depleted_account_still_tops_up_to_its_new_allowance(tenant_factory):
    """The clamp must not become an off switch: below the allowance, top-up still happens."""
    tenant = tenant_factory(entitlements.FREE)
    with SessionLocal() as s:
        account = s.get(Account, tenant.account_id)
        credits.grant_monthly(s, account, ref_id=f"test:{uuid.uuid4().hex}")
        s.commit()
        # Spend nearly all of it, then open a new cycle.
        credits.debit_run(s, tenant.account_id, 95, source="run")
        account.grant_cycle_anchor = None
        s.commit()
        credits.grant_monthly(s, account, ref_id=f"test:{uuid.uuid4().hex}")
        s.commit()
        balance = credits.balance_micro(s, tenant.account_id)

    assert balance == entitlements.limits(entitlements.FREE).monthly_credits * credits.MICRO


@requires_db
def test_a_no_op_grant_still_anchors_the_cycle(tenant_factory):
    """When there's nothing to add, the month must still count as granted — otherwise
    `ensure_current_grant` retries on every single run for the rest of the month."""
    tenant = tenant_factory(entitlements.PLUS)
    with SessionLocal() as s:
        account = s.get(Account, tenant.account_id)
        credits.grant_monthly(s, account, ref_id=f"test:{uuid.uuid4().hex}")
        s.commit()

    _downgrade(tenant.account_id, changed_days_ago=0)
    with SessionLocal() as s:
        account = s.get(Account, tenant.account_id)
        account.grant_cycle_anchor = None
        s.commit()
        assert credits.grant_monthly(s, account, ref_id=f"test:{uuid.uuid4().hex}") is True
        s.commit()
        assert s.get(Account, tenant.account_id).grant_cycle_anchor is not None
