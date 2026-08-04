"""The property the whole account-deletion design exists for: a deleted account stays deleted.

`resolve_account` is find-or-create and `deps.py` commits it on **every** request, so before
0017 a soft-delete was undone by the next page load — the user's own dashboard would silently
rebuild the account they had just asked us to destroy. These tests are the proof that it can't,
and they are deliberately the *first* thing built: until this holds, shipping a delete button
means shipping a no-op.

Two halves:

- **While marked** — resolution raises `CY001`, no row is recreated, and every entry point 401s.
- **After the purge** — the same user resolves again and gets a genuinely *new* account, because
  the purge frees the `owner_user_id` slot rather than leaving a tombstone that locks them out
  of ever signing up again.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import deps
from calypr_api.config import settings
from calypr_api.db.models import Account, Workspace
from calypr_api.db.session import SessionLocal, engine
from calypr_api.main import app
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

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


def _hdr(user_id: str) -> dict[str, str]:
    return {"x-calypr-internal-key": INTERNAL_KEY, "x-calypr-user-id": user_id}


@pytest.fixture
def user(monkeypatch):
    """A signed-in user with enforcement on, cleaned up afterwards."""
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    uid = f"del-test-{uuid.uuid4().hex[:10]}"
    yield uid
    with SessionLocal() as s:
        s.query(Account).filter(Account.owner_user_id == uid).delete(synchronize_session=False)
        s.commit()


def _resolve(user_id: str) -> uuid.UUID:
    with SessionLocal() as s:
        acc = s.execute(text("SELECT resolve_account(:u)"), {"u": user_id}).scalar_one()
        s.commit()
        return uuid.UUID(str(acc))


def _soft_delete(account_id: uuid.UUID) -> None:
    with SessionLocal() as s:
        s.execute(
            text("UPDATE billing_account SET deleted_at = now() WHERE id = :a"),
            {"a": str(account_id)},
        )
        s.commit()


def _counts(user_id: str) -> tuple[int, int]:
    """(accounts for this user, workspaces under them)."""
    with SessionLocal() as s:
        accounts = s.query(Account).filter(Account.owner_user_id == user_id).all()
        ids = [a.id for a in accounts]
        workspaces = (
            s.query(Workspace).filter(Workspace.account_id.in_(ids)).count() if ids else 0
        )
        return len(accounts), workspaces


# --- while marked deleted ----------------------------------------------------------------------


@requires_db
def test_resolution_raises_cy001_and_creates_nothing(user):
    """The headline. Resolution fails with the documented SQLSTATE, and — the part that actually
    matters — the database is left exactly as it was."""
    account_id = _resolve(user)
    assert _counts(user) == (1, 1)
    _soft_delete(account_id)

    with SessionLocal() as s, pytest.raises(DBAPIError) as caught:
        s.execute(text("SELECT resolve_workspace(:u, NULL::uuid)"), {"u": user})

    # Assert the **code**, never the message: the message is a human string free to be reworded,
    # and matching it would turn a copy-edit in a migration into an auth bypass.
    assert caught.value.orig.sqlstate == "CY001"
    assert deps.is_account_deleted(caught.value)

    # No resurrection: not a second account, and not a fresh 'Personal' workspace under the
    # existing one. This is the assert that fails if the guard is moved outside the upsert.
    assert _counts(user) == (1, 1)


@requires_db
def test_tenant_routes_401(user):
    """`tenant` — the data routes."""
    account_id = _resolve(user)
    assert client.get("/workspaces/current", headers=_hdr(user)).status_code == 200
    _soft_delete(account_id)
    assert client.get("/workspaces/current", headers=_hdr(user)).status_code == 401


@requires_db
def test_list_workspaces_401(user):
    """`GET /workspaces` — reached through `tenant`, so it 401s rather than 500ing on
    `list_account_workspaces`, which calls `resolve_account` by name."""
    account_id = _resolve(user)
    assert client.get("/workspaces", headers=_hdr(user)).status_code == 200
    _soft_delete(account_id)
    assert client.get("/workspaces", headers=_hdr(user)).status_code == 401


@requires_db
def test_request_workspace_401(user):
    """`request_workspace` — the compute routes' resolver, which holds no request session."""
    account_id = _resolve(user)
    _soft_delete(account_id)

    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in _hdr(user).items()],
    }
    from fastapi import Request

    with pytest.raises(HTTPException) as caught:
        deps.request_workspace(Request(scope))
    assert caught.value.status_code == 401


@requires_db
def test_run_workspace_401_rather_than_falling_back_to_dev(user):
    """**The regression this file exists to guard.**

    `run_workspace` ends in a blanket `except Exception: return dev` so the playground always
    streams. If the deleted-account check sits *after* that, a deleted account keeps running
    graphs — metered against, and debited from, the shared dev account — and every other assert
    here still passes. So this asserts the 401 explicitly, and that the answer is not the dev
    workspace."""
    account_id = _resolve(user)
    _soft_delete(account_id)

    from fastapi import Request

    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in _hdr(user).items()],
    }
    with pytest.raises(HTTPException) as caught:
        deps.run_workspace(Request(scope))
    assert caught.value.status_code == 401


@requires_db
def test_run_workspace_still_falls_back_for_ordinary_failures(monkeypatch):
    """The control for the test above: the blanket fallback must survive. An anonymous caller —
    no internal key presented — still gets the dev workspace rather than an exception, because
    the public playground is anonymous by design."""
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    from fastapi import Request

    scope = {"type": "http", "headers": []}
    assert deps.run_workspace(Request(scope)) == uuid.UUID(
        "00000000-0000-0000-0000-000000000001"
    )


@requires_db
def test_the_guard_is_off_without_an_internal_key(monkeypatch, user):
    """The dev/CI carve-out. `start.sh` promises the app runs with no database at all, and every
    resolver short-circuits to the dev workspace before touching one — so a soft-deleted account
    is simply not a concept that exists locally. CI runs entirely on this path."""
    account_id = _resolve(user)
    _soft_delete(account_id)
    monkeypatch.setattr(settings, "internal_key", "")

    dev = uuid.UUID("00000000-0000-0000-0000-000000000001")
    from fastapi import Request

    scope = {"type": "http", "headers": []}
    assert deps.request_workspace(Request(scope)) == dev
    assert deps.run_workspace(Request(scope)) == dev


# --- after the purge ---------------------------------------------------------------------------


@requires_db
def test_resolution_works_again_once_the_row_is_gone(user):
    """The purge hard-deletes rather than leaving a tombstone, and this is why: the same person
    signing up again must get a clean account, not a permanent lockout. A returning user is a
    good outcome, and `owner_user_id` is UNIQUE — a tombstone would hold that slot forever."""
    first = _resolve(user)
    _soft_delete(first)

    # What the purge's final step does.
    with SessionLocal() as s:
        s.execute(text("DELETE FROM billing_account WHERE id = :a"), {"a": str(first)})
        s.commit()

    second = _resolve(user)
    assert second != first
    assert _counts(user) == (1, 1)
    assert client.get("/workspaces/current", headers=_hdr(user)).status_code == 200
