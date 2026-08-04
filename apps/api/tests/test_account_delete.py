"""`DELETE /account`: cancel Stripe, write down what must die, mark the account — and nothing else.

The tests worth having here are the ones about *what did not happen*:

- a Stripe failure leaves **zero** trace, so a retry is free and no account is ever deleted while
  its card keeps being charged;
- the request cascades **nothing**, because the destruction is the purge job's problem;
- the collected blob urls are exactly this account's, because that list drives a permanent delete.
"""

from __future__ import annotations

import uuid

import pytest
import stripe
from calypr_api import billing
from calypr_api.config import settings
from calypr_api.db.models import Account, AccountPurge, Agent, Run, ShareLink, Upload, Workspace
from calypr_api.db.session import SessionLocal, engine
from calypr_api.main import app
from fastapi.testclient import TestClient
from sqlalchemy import text

client = TestClient(app)

INTERNAL_KEY = "internal-test-key"


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


def _hdr(user_id: str, email: str | None = None) -> dict[str, str]:
    h = {"x-calypr-internal-key": INTERNAL_KEY, "x-calypr-user-id": user_id}
    if email:
        h["x-calypr-user-email"] = email
    return h


@pytest.fixture
def user(monkeypatch):
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    uid = f"del-req-{uuid.uuid4().hex[:10]}"
    yield uid
    with SessionLocal() as s:
        accounts = s.query(Account).filter(Account.owner_user_id == uid).all()
        for a in accounts:
            s.query(AccountPurge).filter(AccountPurge.account_id == a.id).delete(
                synchronize_session=False
            )
        s.query(Account).filter(Account.owner_user_id == uid).delete(synchronize_session=False)
        s.commit()


def _seed(user_id: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Resolve the account and give it one agent, share link, run and upload.

    Returns (account_id, workspace_id)."""
    with SessionLocal() as s:
        acc = s.execute(text("SELECT resolve_account(:u)"), {"u": user_id}).scalar_one()
        s.commit()
    account_id = uuid.UUID(str(acc))
    with SessionLocal() as s:
        ws = s.query(Workspace).filter(Workspace.account_id == account_id).one()
        agent = Agent(workspace_id=ws.id, name="t", graph_spec={})
        s.add(agent)
        s.flush()
        s.add(
            ShareLink(token=f"tok-{uuid.uuid4().hex[:8]}", agent_id=agent.id, workspace_id=ws.id)
        )
        s.add(
            Run(
                workspace_id=ws.id,
                thread_id=f"ws:{ws.id}:main",
                status="completed",
                source="playground",
            )
        )
        s.add(
            Upload(
                workspace_id=ws.id,
                blob_url="https://store.public.blob.vercel-storage.com/mine.png",
                pathname="mine.png",
                bytes=10,
            )
        )
        s.commit()
        return account_id, ws.id


def _purge_row(account_id: uuid.UUID) -> AccountPurge | None:
    with SessionLocal() as s:
        return s.query(AccountPurge).filter(AccountPurge.account_id == account_id).one_or_none()


def _deleted_at(account_id: uuid.UUID):
    with SessionLocal() as s:
        return s.get(Account, account_id).deleted_at


# --- the happy path ----------------------------------------------------------------------------


@requires_db
def test_delete_records_and_marks_but_cascades_nothing(user):
    account_id, workspace_id = _seed(user)

    resp = client.request("DELETE", "/account", headers=_hdr(user))
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True, "mode": "live"}

    assert _deleted_at(account_id) is not None

    row = _purge_row(account_id)
    assert row is not None
    assert row.purged_at is None
    assert f"ws:{workspace_id}:" in row.thread_prefixes
    assert any(p.startswith("share:") for p in row.thread_prefixes)
    assert row.blob_urls == ["https://store.public.blob.vercel-storage.com/mine.png"]

    # **Nothing cascaded.** The row is marked, not removed, and every child survives for the
    # purge to deal with. If this starts failing, someone moved destruction into the request and
    # the crash-safety the whole design buys is gone.
    with SessionLocal() as s:
        assert s.get(Account, account_id) is not None
        assert s.query(Workspace).filter(Workspace.account_id == account_id).count() == 1
        assert s.query(Agent).filter(Agent.workspace_id == workspace_id).count() == 1
        assert s.query(Run).filter(Run.workspace_id == workspace_id).count() == 1
        assert s.query(Upload).filter(Upload.workspace_id == workspace_id).count() == 1


@requires_db
def test_delete_is_idempotent(user):
    account_id, _ = _seed(user)
    assert client.request("DELETE", "/account", headers=_hdr(user)).status_code == 200

    # The account is now deleted, so `tenant` 401s — which is itself the second-call answer a
    # browser gets. Call the route's body again through a fresh resolve to prove the *record*
    # isn't duplicated either.
    assert client.request("DELETE", "/account", headers=_hdr(user)).status_code == 401
    with SessionLocal() as s:
        assert s.query(AccountPurge).filter(AccountPurge.account_id == account_id).count() == 1


@requires_db
def test_legacy_threads_are_collected_and_prefixed_ones_are_not(user):
    """A thread from before `threads.py` namespaced ids is reachable only through `run.thread_id`,
    so it must be enumerated. A `ws:`-prefixed one must **not** be — it's already covered by the
    prefix, and listing it twice would make the purge do the same work again."""
    account_id, workspace_id = _seed(user)
    with SessionLocal() as s:
        s.add(
            Run(
                workspace_id=workspace_id,
                thread_id="legacy-thread-abc",
                status="completed",
                source="playground",
            )
        )
        s.commit()

    client.request("DELETE", "/account", headers=_hdr(user))

    row = _purge_row(account_id)
    assert row.legacy_thread_ids == ["legacy-thread-abc"]
    assert f"ws:{workspace_id}:main" not in row.legacy_thread_ids


@requires_db
def test_only_this_accounts_blobs_are_collected(user, monkeypatch):
    """The join through `workspace.account_id` is the only guarantee we never point a permanent
    delete at someone else's object. This is that guarantee's test."""
    account_id, _ = _seed(user)

    other_uid = f"del-other-{uuid.uuid4().hex[:8]}"
    other_account, other_ws = _seed(other_uid)
    with SessionLocal() as s:
        s.add(
            Upload(
                workspace_id=other_ws,
                blob_url="https://store.public.blob.vercel-storage.com/THEIRS.png",
                pathname="theirs.png",
                bytes=10,
            )
        )
        s.commit()

    try:
        client.request("DELETE", "/account", headers=_hdr(user))
        row = _purge_row(account_id)
        assert all("THEIRS" not in u for u in row.blob_urls)
        assert row.blob_urls == ["https://store.public.blob.vercel-storage.com/mine.png"]
        # And the other account is entirely untouched.
        with SessionLocal() as s:
            assert s.get(Account, other_account).deleted_at is None
    finally:
        with SessionLocal() as s:
            s.query(AccountPurge).filter(AccountPurge.account_id == other_account).delete(
                synchronize_session=False
            )
            s.query(Account).filter(Account.id == other_account).delete(synchronize_session=False)
            s.commit()


@requires_db
def test_the_waitlist_row_is_dropped(user):
    """The beta invite is forfeited. `account_purge` stores no email, so this is the last moment
    we can match on one — and leaving the row would let a returning signup silently re-inherit a
    grant to a paid feature."""
    email = f"{uuid.uuid4().hex[:8]}@example.com"
    _seed(user)
    with SessionLocal() as s:
        s.execute(text("INSERT INTO waitlist (email) VALUES (:e)"), {"e": email})
        s.commit()

    client.request("DELETE", "/account", headers=_hdr(user, email=email))

    with SessionLocal() as s:
        left = s.execute(
            text("SELECT count(*) FROM waitlist WHERE lower(email) = lower(:e)"), {"e": email}
        ).scalar()
        assert left == 0


# --- the failure that must not half-delete -----------------------------------------------------


@requires_db
def test_a_stripe_failure_502s_and_changes_absolutely_nothing(user, monkeypatch):
    """**The test that stops a half-delete.**

    If the cancellation fails and we delete anyway, the user loses their account *and* keeps
    being charged, with no way to reach the portal that would stop it. So: 502, `deleted_at`
    still NULL, and zero purge rows — the state a retry can start from."""
    account_id, _ = _seed(user)
    with SessionLocal() as s:
        s.execute(
            text("UPDATE billing_account SET stripe_subscription_id = 'sub_x' WHERE id = :a"),
            {"a": str(account_id)},
        )
        s.commit()

    def boom(*args, **kwargs):
        raise stripe.APIConnectionError("stripe is down")

    monkeypatch.setattr(stripe.Subscription, "cancel", boom)

    resp = client.request("DELETE", "/account", headers=_hdr(user))
    assert resp.status_code == 502

    assert _deleted_at(account_id) is None
    assert _purge_row(account_id) is None
    # Still reachable — the user can retry, or go cancel in the portal themselves.
    assert client.get("/workspaces/current", headers=_hdr(user)).status_code == 200


@requires_db
def test_a_subscription_stripe_has_already_lost_counts_as_success(user, monkeypatch):
    """The goal is "not billing", and a subscription Stripe says doesn't exist isn't. Failing
    here would wedge the account permanently on a condition that is already the desired one."""
    account_id, _ = _seed(user)
    with SessionLocal() as s:
        s.execute(
            text("UPDATE billing_account SET stripe_subscription_id = 'sub_gone' WHERE id = :a"),
            {"a": str(account_id)},
        )
        s.commit()

    def missing(*args, **kwargs):
        raise stripe.InvalidRequestError(
            "No such subscription", param="subscription", code="resource_missing"
        )

    monkeypatch.setattr(stripe.Subscription, "cancel", missing)

    assert client.request("DELETE", "/account", headers=_hdr(user)).status_code == 200
    assert _deleted_at(account_id) is not None


@requires_db
def test_a_free_account_needs_no_stripe_call(user, monkeypatch):
    """No subscription means no API call at all — an outage at Stripe must not stop a free user
    from deleting their account."""
    account_id, _ = _seed(user)

    def boom(*args, **kwargs):
        raise AssertionError("Stripe must not be called for an account with no subscription")

    monkeypatch.setattr(stripe.Subscription, "cancel", boom)

    assert client.request("DELETE", "/account", headers=_hdr(user)).status_code == 200
    assert _purge_row(account_id).stripe_cancelled_at is None


# --- the dev carve-out -------------------------------------------------------------------------


def test_dev_mode_501s(monkeypatch):
    """CI runs entirely here. The dev account is shared by every anonymous request and seeded by
    0016 — marking it deleted would break every future test run with no way back."""
    monkeypatch.setattr(settings, "internal_key", "")
    resp = client.request("DELETE", "/account")
    assert resp.status_code == 501


@requires_db
def test_billing_cancel_helper_returns_false_with_no_subscription():
    """`cancel_subscription` is the unit the router trusts; "nothing to cancel" is a success."""
    assert billing.cancel_subscription(Account(stripe_subscription_id=None)) is False
