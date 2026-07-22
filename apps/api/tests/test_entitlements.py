"""Entitlements + the beta-access surfaces: waitlist capture and the operator promote route.

The DB-backed cases skip without a database (same pattern as `test_engine_api.py`); CI provides
Postgres and runs `alembic upgrade head` before pytest.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import deps, entitlements
from calypr_api.config import settings
from calypr_api.db.models import Waitlist, Workspace
from calypr_api.db.session import SessionLocal, engine
from calypr_api.main import app
from calypr_codegen import generate_python
from calypr_compiler.golden import input_agent_output
from fastapi.testclient import TestClient
from sqlalchemy import select, text

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


# --- the invite list: waitlist rows with `invited_at` set -------------------------------------


@requires_db
def test_invite_stamps_existing_signups_and_adds_new_ones(monkeypatch):
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    joined = f"joined.{uuid.uuid4().hex[:8]}@example.com"
    never = f"never.{uuid.uuid4().hex[:8]}@example.com"
    client.post("/waitlist", json={"email": joined})

    r = client.post(
        "/admin/invite",
        json={"emails": [joined.upper(), never]},  # case shouldn't matter
        headers={"x-admin-token": ADMIN_TOKEN},
    )
    assert r.status_code == 200
    assert set(r.json()["invited"]) == {joined, never}

    # Re-running an invite is safe — nothing changes the second time.
    again = client.post(
        "/admin/invite", json={"emails": [joined]}, headers={"x-admin-token": ADMIN_TOKEN}
    ).json()
    assert again["invited"] == []
    assert again["already_invited"] == [joined]


@requires_db
def test_invited_email_auto_grants_beta_on_sign_in(monkeypatch):
    # The point of the invite list: stamp an address, they sign in, beta switches on by itself.
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    email = f"partner.{uuid.uuid4().hex[:8]}@example.com"
    client.post("/admin/invite", json={"emails": [email]}, headers={"x-admin-token": ADMIN_TOKEN})

    with SessionLocal() as s:
        ws = s.query(Workspace).first()
        if ws is None:
            pytest.skip("no workspace rows")
        original, ws.plan = ws.plan, entitlements.FREE
        s.commit()

        assert entitlements.grant_beta_if_invited(s, ws, email) is True
        assert ws.plan == entitlements.BETA
        # Idempotent: a second sign-in changes nothing.
        assert entitlements.grant_beta_if_invited(s, ws, email) is False

        ws.plan = original
        s.commit()


@requires_db
def test_joining_the_waitlist_is_not_enough_to_get_beta():
    # The distinction that makes this a *closed* beta: on the list ≠ invited.
    email = f"pending.{uuid.uuid4().hex[:8]}@example.com"
    client.post("/waitlist", json={"email": email})

    with SessionLocal() as s:
        assert entitlements.is_invited(s, email) is False
        ws = s.query(Workspace).first()
        if ws is None:
            pytest.skip("no workspace rows")
        original, ws.plan = ws.plan, entitlements.FREE
        s.commit()
        assert entitlements.grant_beta_if_invited(s, ws, email) is False
        assert ws.plan == entitlements.FREE
        ws.plan = original
        s.commit()


@requires_db
def test_a_stranger_never_gets_beta():
    with SessionLocal() as s:
        assert entitlements.is_invited(s, f"stranger.{uuid.uuid4().hex[:8]}@example.com") is False
        assert entitlements.is_invited(s, None) is False
        assert entitlements.is_invited(s, "") is False


@requires_db
def test_auto_grant_never_downgrades_or_touches_plus(monkeypatch):
    # One-way and only from `free`, so the manual admin route stays authoritative.
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    email = f"plusser.{uuid.uuid4().hex[:8]}@example.com"
    client.post("/admin/invite", json={"emails": [email]}, headers={"x-admin-token": ADMIN_TOKEN})

    with SessionLocal() as s:
        ws = s.query(Workspace).first()
        if ws is None:
            pytest.skip("no workspace rows")
        original, ws.plan = ws.plan, entitlements.PLUS
        s.commit()
        assert entitlements.grant_beta_if_invited(s, ws, email) is False
        assert ws.plan == entitlements.PLUS, "a plus workspace must not be downgraded to beta"
        ws.plan = original
        s.commit()


# --- admin routes fail closed ----------------------------------------------------------------


def test_admin_routes_404_without_a_configured_token(monkeypatch):
    # Unset token (the default, incl. CI and any accidental deploy) ⇒ the routes don't exist.
    monkeypatch.delenv("CALYPR_ADMIN_TOKEN", raising=False)
    assert client.get("/admin/waitlist").status_code == 404
    assert client.post("/admin/invite", json={"emails": ["x@example.com"]}).status_code == 404
    assert (
        client.post(f"/admin/workspaces/{uuid.uuid4()}/plan", json={"plan": "beta"}).status_code
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


# --- the paywall on /parse (code export) ------------------------------------------------------
#
# `flags.ts` hides the UI, but the endpoint is what actually has to say no — otherwise the paid
# feature is free to anyone who posts to it directly.


def _parse_body() -> dict:
    return {"code": generate_python(input_agent_output(model="fake"))}


def test_parse_is_open_when_no_internal_key_is_set(monkeypatch):
    # The dev/CI carve-out: without an internal key every request is the shared dev workspace
    # (`free`), so enforcing there would make the export path untestable — locally and in the
    # e2e suite. Deployments always set a key.
    monkeypatch.setattr(settings, "internal_key", None)
    assert client.post("/parse", json=_parse_body()).status_code == 200


@requires_db
def test_parse_402s_for_a_workspace_that_has_not_paid(monkeypatch):
    monkeypatch.setattr(settings, "internal_key", "internal-test-key")
    with SessionLocal() as s:
        ws = s.query(Workspace).first()
        if ws is None:
            pytest.skip("no workspace rows")
        ws_id, original, ws.plan = ws.id, ws.plan, entitlements.FREE
        s.commit()
    monkeypatch.setattr(deps, "_resolve_workspace_id", lambda request, session: ws_id)
    try:
        r = client.post("/parse", json=_parse_body())
        assert r.status_code == 402
        assert r.json()["detail"]["feature"] == "code_export"
    finally:
        with SessionLocal() as s:
            s.query(Workspace).filter(Workspace.id == ws_id).update({"plan": original})
            s.commit()


@requires_db
@pytest.mark.parametrize("plan", [entitlements.BETA, entitlements.PLUS])
def test_parse_serves_an_entitled_workspace(monkeypatch, plan: str):
    monkeypatch.setattr(settings, "internal_key", "internal-test-key")
    with SessionLocal() as s:
        ws = s.query(Workspace).first()
        if ws is None:
            pytest.skip("no workspace rows")
        ws_id, original, ws.plan = ws.id, ws.plan, plan
        s.commit()
    monkeypatch.setattr(deps, "_resolve_workspace_id", lambda request, session: ws_id)
    try:
        r = client.post("/parse", json=_parse_body())
        assert r.status_code == 200
        assert r.json()["graph"]["nodes"], "an entitled caller still gets a parsed graph"
    finally:
        with SessionLocal() as s:
            s.query(Workspace).filter(Workspace.id == ws_id).update({"plan": original})
            s.commit()


# --- the code preview on /codegen -------------------------------------------------------------
#
# `/codegen` always answers — opening a tab should never be an error — so the gate here is how
# *much* of the file comes back. The cut is server-side: a CSS blur over a full response is a
# decoration, not a paywall.


def _graph() -> dict:
    return input_agent_output(model="fake").model_dump(mode="json")


def test_codegen_returns_the_whole_file_when_no_internal_key_is_set(monkeypatch):
    monkeypatch.setattr(settings, "internal_key", None)
    body = client.post("/codegen", json=_graph()).json()
    assert body["truncated"] is False
    assert "def build_graph" in body["code"]
    assert body["code"].count("\n") + 1 == body["total_lines"]


@requires_db
@pytest.mark.parametrize(
    ("plan", "expect_truncated"),
    [
        (entitlements.FREE, True),
        (entitlements.PLUS, False),
        (entitlements.BETA, False),
    ],
)
def test_codegen_serves_the_file_only_to_an_entitled_plan(monkeypatch, plan, expect_truncated):
    """Both outcomes through the same code path, so the truncation is demonstrably driven by
    the plan column — not by an unresolvable user, which is a different reason to get a
    preview and would make a free-only test pass for the wrong reason."""
    monkeypatch.setattr(settings, "internal_key", "internal-test-key")
    with SessionLocal() as s:
        ws = s.query(Workspace).first()
        if ws is None:
            pytest.skip("no workspace rows")
        ws_id, original, ws.plan = ws.id, ws.plan, plan
        s.commit()
    monkeypatch.setattr(deps, "_resolve_workspace_id", lambda request, session: ws_id)
    try:
        r = client.post(
            "/codegen",
            json=_graph(),
            headers={"x-calypr-internal-key": "internal-test-key", "x-calypr-user-id": "u"},
        )
        body = r.json()
        assert r.status_code == 200, "opening the Code tab must never error"
        assert body["truncated"] is expect_truncated
        if expect_truncated:
            # The preview is real, readable code — that's what makes it worth upgrading for —
            # but it must stop before the part being sold.
            assert "import" in body["code"]
            assert "def build_graph" not in body["code"]
            assert body["total_lines"] > body["code"].count("\n")
        else:
            assert "def build_graph" in body["code"]
    finally:
        with SessionLocal() as s:
            s.query(Workspace).filter(Workspace.id == ws_id).update({"plan": original})
            s.commit()


def test_codegen_previews_for_a_signed_out_caller(monkeypatch):
    # No user id behind a configured internal key = signed out. Preview, not 401.
    monkeypatch.setattr(settings, "internal_key", "internal-test-key")
    r = client.post(
        "/codegen", json=_graph(), headers={"x-calypr-internal-key": "internal-test-key"}
    )
    assert r.status_code == 200
    assert r.json()["truncated"] is True


def test_codegen_previews_when_the_internal_key_is_wrong(monkeypatch):
    # Fail closed: a misconfigured proxy must not hand out the paid artifact.
    monkeypatch.setattr(settings, "internal_key", "internal-test-key")
    r = client.post("/codegen", json=_graph(), headers={"x-calypr-internal-key": "wrong"})
    assert r.json()["truncated"] is True


# --- an invite is a one-time key, not a standing entitlement ------------------------------------


@requires_db
def test_a_demotion_sticks_after_the_invite_has_been_redeemed(monkeypatch):
    """The scenario that matters when the beta ends: demote someone to `free`, and they must
    *stay* free through their next sign-in.

    Before `granted_at`, the auto-grant re-ran on every sign-in, so this silently put them back
    on `beta` — every demotion undid itself and the admin route only looked authoritative."""
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    email = f"trial.{uuid.uuid4().hex[:8]}@example.com"
    client.post("/admin/invite", json={"emails": [email]}, headers={"x-admin-token": ADMIN_TOKEN})

    with SessionLocal() as s:
        ws = s.query(Workspace).first()
        if ws is None:
            pytest.skip("no workspace rows")
        original, ws.plan = ws.plan, entitlements.FREE
        s.commit()
        try:
            # Day 1: they sign in and the invite is redeemed.
            assert entitlements.grant_beta_if_invited(s, ws, email) is True
            assert ws.plan == entitlements.BETA
            s.commit()

            # Day 14: the trial ends and we put them back on free.
            ws.plan = entitlements.FREE
            s.commit()

            # Day 15: they sign in again. The invite is spent, so nothing happens.
            assert entitlements.grant_beta_if_invited(s, ws, email) is False
            assert ws.plan == entitlements.FREE, "a demotion must survive the next sign-in"
        finally:
            ws.plan = original
            s.commit()


@requires_db
def test_re_inviting_someone_lets_them_back_in(monkeypatch):
    """The deliberate way back: stamp a fresh invite and the key works again. Demoting is
    reversible without touching workspace ids by hand."""
    monkeypatch.setenv("CALYPR_ADMIN_TOKEN", ADMIN_TOKEN)
    email = f"return.{uuid.uuid4().hex[:8]}@example.com"
    client.post("/admin/invite", json={"emails": [email]}, headers={"x-admin-token": ADMIN_TOKEN})

    with SessionLocal() as s:
        ws = s.query(Workspace).first()
        if ws is None:
            pytest.skip("no workspace rows")
        original, ws.plan = ws.plan, entitlements.FREE
        s.commit()
        try:
            assert entitlements.grant_beta_if_invited(s, ws, email) is True
            ws.plan = entitlements.FREE
            s.commit()
            assert entitlements.grant_beta_if_invited(s, ws, email) is False

            # Clearing the redemption is what "invite them again" means.
            row = s.scalar(select(Waitlist).where(Waitlist.email == email))
            row.granted_at = None
            s.commit()
            assert entitlements.grant_beta_if_invited(s, ws, email) is True
            assert ws.plan == entitlements.BETA
        finally:
            ws.plan = original
            s.commit()
