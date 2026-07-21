"""Entitlements + the beta-access surfaces: waitlist capture and the operator promote route.

The DB-backed cases skip without a database (same pattern as `test_engine_api.py`); CI provides
Postgres and runs `alembic upgrade head` before pytest.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import entitlements
from calypr_api.db.session import SessionLocal, engine
from calypr_api.main import app
from fastapi.testclient import TestClient
from sqlalchemy import text

client = TestClient(app)

ADMIN_TOKEN = "test-admin-token"


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


# --- pure entitlement rules ------------------------------------------------------------------


def test_only_beta_and_plus_get_the_roundtrip():
    # `beta` gates on our confidence, `plus` on value capture — both currently unlock it, and
    # `free` doesn't. When the round-trip graduates to free-for-all this becomes one edit.
    assert entitlements.has_roundtrip("beta") is True
    assert entitlements.has_roundtrip("plus") is True
    assert entitlements.has_roundtrip("free") is False


def test_unknown_or_missing_plan_is_not_entitled():
    # Fail closed: a null column, a typo, or a plan from a future release grants nothing.
    assert entitlements.has_roundtrip(None) is False
    assert entitlements.has_roundtrip("") is False
    assert entitlements.has_roundtrip("enterprise") is False


def test_plan_validation():
    assert all(entitlements.is_valid_plan(p) for p in entitlements.PLANS)
    assert entitlements.is_valid_plan("gold") is False


@requires_db
def test_current_workspace_reports_its_plan():
    # The client gates the beta UI on this field, so it has to be present and default to `free`.
    r = client.get("/workspaces/current")
    assert r.status_code == 200
    body = r.json()
    assert "plan" in body
    assert body["plan"] in entitlements.PLANS


# --- waitlist --------------------------------------------------------------------------------


@requires_db
def test_waitlist_normalizes_and_is_idempotent(monkeypatch):
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    email = f"Ada.{uuid.uuid4().hex[:8]}@Example.COM"
    normalized = email.strip().lower()

    assert client.post("/waitlist", json={"email": f"  {email} "}).status_code == 204
    # Pressing the button twice is a user being impatient, not an error.
    assert client.post("/waitlist", json={"email": normalized}).status_code == 204

    rows = client.get("/admin/waitlist", headers={"x-admin-token": ADMIN_TOKEN}).json()
    matches = [r for r in rows if r["email"] == normalized]
    assert len(matches) == 1, "duplicate submit created a second row"
    assert matches[0]["invited_at"] is None


@pytest.mark.parametrize(
    "bad",
    [
        "not-an-address",
        "missing@tld",
        "grace, hopper@example.com",  # pasted a list
        "Ada <ada@example.com>",  # pasted a display name
        "two@@example.com",
        "@example.com",
        "trailing@example.",
    ],
)
def test_waitlist_rejects_a_non_email(bad: str):
    assert client.post("/waitlist", json={"email": bad}).status_code == 422


@pytest.mark.parametrize(
    "good", ["ada@example.com", "ada.lovelace+beta@sub.example.co.uk", "a@b.io"]
)
def test_waitlist_accepts_real_addresses(good: str):
    # 422 would mean the validator is too strict; anything else (204, or a DB error in a
    # no-database environment) means it passed validation.
    assert client.post("/waitlist", json={"email": good}).status_code != 422


@requires_db
def test_waitlist_join_never_returns_rows():
    # Write-only by construction: the public route must not be an enumeration oracle.
    r = client.post("/waitlist", json={"email": f"probe.{uuid.uuid4().hex[:8]}@example.com"})
    assert r.status_code == 204
    assert r.content in (b"", None)


# --- admin routes fail closed ----------------------------------------------------------------


def test_admin_routes_404_without_a_configured_token(monkeypatch):
    # Unset token (the default, incl. CI and any accidental deploy) ⇒ the routes don't exist.
    monkeypatch.delenv("CALYPR_ADMIN_TOKEN", raising=False)
    assert client.get("/admin/waitlist").status_code == 404
    assert (
        client.post(
            f"/admin/workspaces/{uuid.uuid4()}/plan", json={"plan": "beta"}
        ).status_code
        == 404
    )


def test_admin_routes_404_on_a_wrong_token(monkeypatch):
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    # 404 rather than 403 so the routes' existence isn't advertised.
    assert client.get("/admin/waitlist", headers={"x-admin-token": "guess"}).status_code == 404


# --- promoting a workspace into the beta ------------------------------------------------------


@requires_db
def test_promote_workspace_to_beta_and_stamp_the_invite(monkeypatch):
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    email = f"partner.{uuid.uuid4().hex[:8]}@example.com"
    client.post("/waitlist", json={"email": email})

    with SessionLocal() as s:
        ws_id = s.execute(text("SELECT id FROM workspace LIMIT 1")).scalar()
        original = s.execute(
            text("SELECT plan FROM workspace WHERE id = :i"), {"i": ws_id}
        ).scalar()
    if ws_id is None:
        pytest.skip("no workspace rows to promote")

    try:
        r = client.post(
            f"/admin/workspaces/{ws_id}/plan",
            json={"plan": "beta", "email": email},
            headers={"x-admin-token": ADMIN_TOKEN},
        )
        assert r.status_code == 200
        assert r.json()["plan"] == "beta"

        rows = client.get("/admin/waitlist", headers={"x-admin-token": ADMIN_TOKEN}).json()
        entry = next(r for r in rows if r["email"] == email)
        assert entry["invited_at"] is not None, "promotion should stamp the waitlist row"
    finally:
        # Leave the shared dev workspace as we found it — e2e asserts the round-trip UI is
        # hidden for a `free` workspace and runs against this same database.
        client.post(
            f"/admin/workspaces/{ws_id}/plan",
            json={"plan": original or "free"},
            headers={"x-admin-token": ADMIN_TOKEN},
        )


@requires_db
def test_promote_rejects_an_unknown_plan(monkeypatch):
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    with SessionLocal() as s:
        ws_id = s.execute(text("SELECT id FROM workspace LIMIT 1")).scalar()
    if ws_id is None:
        pytest.skip("no workspace rows")
    r = client.post(
        f"/admin/workspaces/{ws_id}/plan",
        json={"plan": "gold"},
        headers={"x-admin-token": ADMIN_TOKEN},
    )
    assert r.status_code == 422


@requires_db
def test_promote_404s_for_an_unknown_workspace(monkeypatch):
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    r = client.post(
        f"/admin/workspaces/{uuid.uuid4()}/plan",
        json={"plan": "beta"},
        headers={"x-admin-token": ADMIN_TOKEN},
    )
    assert r.status_code == 404
