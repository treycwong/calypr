"""The account/workspace split: pooled caps, cross-account isolation, and the dev carve-out.

Three things are worth testing here and nothing else really is:

1. **Caps pool per account.** A second workspace must not be a way to buy more projects.
2. **A workspace claim is never trusted.** The browser sends one; SQL decides.
3. **The dev/CI carve-out still costs nothing.** `start.sh` promises the app runs with no
   database at all, and every gate added here has to keep that true.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import accounts, deps, entitlements
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import Account, Agent, Workspace
from calypr_api.db.session import SessionLocal, engine
from calypr_api.main import app
from calypr_compiler.golden import input_agent_output
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


def _graph() -> dict:
    return input_agent_output(model="fake").model_dump(mode="json")


def _hdr(user_id: str, workspace_id: uuid.UUID | str | None = None) -> dict[str, str]:
    h = {"x-calypr-internal-key": INTERNAL_KEY, "x-calypr-user-id": user_id}
    if workspace_id is not None:
        h[deps.WORKSPACE_HEADER] = str(workspace_id)
    return h


@pytest.fixture
def user(monkeypatch):
    """A signed-in user id, with enforcement on and their account cleaned up afterwards.

    Fresh per test: `resolve_account` finds-or-creates, so a fixed id would accumulate agents
    across runs and eventually trip the project cap for reasons unrelated to the test."""
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    uid = f"acct-test-{uuid.uuid4().hex[:10]}"
    yield uid
    with SessionLocal() as s:
        s.query(Account).filter(Account.owner_user_id == uid).delete(synchronize_session=False)
        s.commit()


def _set_plan(user_id: str, plan: str) -> uuid.UUID:
    """Put this user's account on `plan`, creating it if needed. Returns the account id."""
    with SessionLocal() as s:
        account_id = s.execute(
            text("SELECT resolve_account(:uid)"), {"uid": user_id}
        ).scalar_one()
        s.get(Account, account_id).plan = plan
        s.commit()
        return account_id


# --- what the switcher is allowed to offer -------------------------------------------------------


@requires_db
def test_free_is_told_it_cannot_create_another_workspace(user):
    """The switcher asks the API rather than deciding for itself.

    On Free the cap is 1 and `resolve_account` guarantees a 'Personal' workspace exists, so
    "New workspace" could never succeed — the menu links to pricing instead of opening a dialog
    whose only outcome is a refusal. This is the answer that drives that."""
    _set_plan(user, entitlements.FREE)
    body = client.get("/workspaces", headers=_hdr(user)).json()

    assert len(body["workspaces"]) == 1
    assert body["plan"] == entitlements.FREE
    assert body["can_create"] is False


@requires_db
def test_plus_may_create_until_it_reaches_the_cap(user):
    """And the boundary is the cap itself, not the plan name — so raising `LIMITS` is the only
    edit needed to change this behaviour."""
    _set_plan(user, entitlements.PLUS)
    cap = entitlements.limits(entitlements.PLUS).workspaces

    body = client.get("/workspaces", headers=_hdr(user)).json()
    assert body["can_create"] is True

    while len(client.get("/workspaces", headers=_hdr(user)).json()["workspaces"]) < cap:
        assert (
            client.post("/workspaces", json={"name": "more"}, headers=_hdr(user)).status_code
            == 201
        )

    body = client.get("/workspaces", headers=_hdr(user)).json()
    assert len(body["workspaces"]) == cap
    assert body["can_create"] is False
    # And the affordance agrees with what the endpoint would actually do.
    assert client.post("/workspaces", json={"name": "x"}, headers=_hdr(user)).status_code == 402


@requires_db
def test_the_switcher_offers_creation_without_an_internal_key(monkeypatch):
    """Dev/CI: caps aren't enforced, so reporting `can_create: false` would hide an affordance
    that demonstrably works locally — and take the e2e coverage of the create flow with it."""
    monkeypatch.setattr(settings, "internal_key", "")
    body = client.get("/workspaces").json()
    assert body["can_create"] is True


# --- the caps pool across an account's workspaces ------------------------------------------------


@requires_db
def test_the_project_cap_pools_across_workspaces(user):
    """The cap is "3 projects", not "3 per workspace".

    This is the whole reason quotas moved to the account. Counting per workspace would make a
    second workspace a way to get more projects for free, which is exactly what someone hitting
    the cap would try first."""
    _set_plan(user, entitlements.FREE)

    # Two of the three free projects in the default workspace.
    for i in range(2):
        r = client.post("/agents", json={"name": f"P{i}", "graph": _graph()}, headers=_hdr(user))
        assert r.status_code == 200

    second = client.post("/workspaces", json={"name": "Side"}, headers=_hdr(user))
    assert second.status_code == 402, "free is capped at one workspace"

    # …so use a Plus account to prove the *project* pooling, which needs two workspaces.
    _set_plan(user, entitlements.PLUS)
    second = client.post("/workspaces", json={"name": "Side"}, headers=_hdr(user))
    assert second.status_code == 201
    second_id = second.json()["id"]

    # Back to free, with 2 projects already used in the *other* workspace. The fresh workspace
    # is empty, and must still only have one slot left.
    _set_plan(user, entitlements.FREE)
    r = client.post(
        "/agents", json={"name": "P3", "graph": _graph()}, headers=_hdr(user, second_id)
    )
    assert r.status_code == 200, "the third project fits, wherever it lives"

    r = client.post(
        "/agents", json={"name": "P4", "graph": _graph()}, headers=_hdr(user, second_id)
    )
    assert r.status_code == 402, "an empty second workspace does not reset the pooled cap"
    detail = r.json()["detail"]
    assert detail["reason"] == "project_cap"
    assert detail["limit"] == 3
    assert "3 of 3" in detail["message"]

    # The affordance and the enforcement are the same predicate, so the dashboard's New Project
    # button cannot offer what `create_agent` would refuse. The browser used to work this out for
    # itself from a plan name and a row count, and got it wrong wherever caps aren't enforced.
    listing = client.get("/workspaces", headers=_hdr(user, second_id))
    assert listing.status_code == 200
    assert listing.json()["can_create_project"] is False


@requires_db
def test_the_workspace_cap_matches_the_plan(user):
    _set_plan(user, entitlements.FREE)
    r = client.post("/workspaces", json={"name": "Second"}, headers=_hdr(user))
    assert r.status_code == 402
    assert r.json()["detail"]["reason"] == "workspace_cap"

    _set_plan(user, entitlements.PLUS)
    # One already exists (the default), so Plus has room for two more.
    assert client.post("/workspaces", json={"name": "B"}, headers=_hdr(user)).status_code == 201
    assert client.post("/workspaces", json={"name": "C"}, headers=_hdr(user)).status_code == 201
    r = client.post("/workspaces", json={"name": "D"}, headers=_hdr(user))
    assert r.status_code == 402, "plus stops at three"
    assert r.json()["detail"]["limit"] == 3


@requires_db
def test_credits_are_pooled_not_per_workspace(user):
    """Granted once to the account, spendable from any of its workspaces — the bug the account
    split exists to prevent is three workspaces meaning 3× the monthly grant."""
    from calypr_api import credits

    account_id = _set_plan(user, entitlements.PLUS)
    assert client.post("/workspaces", json={"name": "B"}, headers=_hdr(user)).status_code == 201

    with SessionLocal() as s:
        acct = s.get(Account, account_id)
        credits.grant_monthly(s, acct, ref_id="test-pool")
        s.commit()
        assert credits.balance_micro(s, account_id) == 2_000 * credits.MICRO
        assert accounts.workspace_count(s, account_id) == 2

    # Spend from one workspace; the other sees the same reduced balance.
    workspaces = client.get("/workspaces", headers=_hdr(user)).json()["workspaces"]
    assert len(workspaces) == 2
    with SessionLocal() as s:
        credits.debit_run(
            s, account_id, 500, source="run", workspace_id=uuid.UUID(workspaces[1]["id"])
        )
        s.commit()

    for ws in workspaces:
        body = client.get("/workspaces/current", headers=_hdr(user, ws["id"])).json()
        assert body["credits"]["remaining"] == 1_500, "one balance, seen from either workspace"


# --- a workspace claim is validated, never trusted -----------------------------------------------


@requires_db
def test_a_foreign_workspace_claim_falls_back_to_your_own(monkeypatch):
    """The security property the switcher rests on.

    A cookie is a UI preference, so a stale or forged one must not error — but it must never
    open someone else's workspace either. Both users are real and both workspaces exist; only
    ownership separates them."""
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    victim = f"victim-{uuid.uuid4().hex[:8]}"
    attacker = f"attacker-{uuid.uuid4().hex[:8]}"
    try:
        victim_ws = client.get("/workspaces/current", headers=_hdr(victim)).json()["id"]
        attacker_ws = client.get("/workspaces/current", headers=_hdr(attacker)).json()["id"]
        assert victim_ws != attacker_ws

        # An agent only the victim should ever see.
        secret = client.post(
            "/agents", json={"name": "Secret", "graph": _graph()}, headers=_hdr(victim)
        )
        assert secret.status_code == 200

        # The attacker claims the victim's workspace by id.
        served = client.get("/workspaces/current", headers=_hdr(attacker, victim_ws)).json()
        assert served["id"] == attacker_ws, "the claim is rejected, in favour of their own"

        listed = client.get("/agents", headers=_hdr(attacker, victim_ws)).json()
        assert all(a["id"] != secret.json()["id"] for a in listed), "no foreign data leaks"
    finally:
        with SessionLocal() as s:
            s.query(Account).filter(
                Account.owner_user_id.in_([victim, attacker])
            ).delete(synchronize_session=False)
            s.commit()


@requires_db
def test_a_malformed_workspace_claim_is_ignored_rather_than_rejected(user):
    """Garbage in the cookie must not 4xx — that would wedge the dashboard with no way back."""
    default = client.get("/workspaces/current", headers=_hdr(user)).json()["id"]
    for claim in ("not-a-uuid", "", str(uuid.uuid4())):
        r = client.get("/workspaces/current", headers=_hdr(user, claim))
        assert r.status_code == 200
        assert r.json()["id"] == default


@requires_db
def test_a_legitimate_second_workspace_is_selectable(user):
    _set_plan(user, entitlements.PLUS)
    created = client.post("/workspaces", json={"name": "Side"}, headers=_hdr(user))
    assert created.status_code == 201
    side = created.json()["id"]

    assert client.get("/workspaces/current", headers=_hdr(user, side)).json()["id"] == side
    listing = client.get("/workspaces", headers=_hdr(user, side)).json()["workspaces"]
    assert {w["name"] for w in listing} == {"Personal", "Side"}
    assert [w["id"] for w in listing if w["is_current"]] == [side]


# --- deleting ------------------------------------------------------------------------------------


@requires_db
def test_the_last_workspace_cannot_be_deleted(user):
    ws_id = client.get("/workspaces/current", headers=_hdr(user)).json()["id"]
    r = client.request("DELETE", f"/workspaces/{ws_id}", headers=_hdr(user))
    assert r.status_code == 400, "an account with no workspace has nowhere to put work"


@requires_db
def test_deleting_frees_a_slot(user):
    """Without this, hitting the workspace cap would be unrecoverable."""
    _set_plan(user, entitlements.PLUS)
    for name in ("B", "C"):
        assert (
            client.post("/workspaces", json={"name": name}, headers=_hdr(user)).status_code == 201
        )
    assert client.post("/workspaces", json={"name": "D"}, headers=_hdr(user)).status_code == 402

    doomed = [
        w
        for w in client.get("/workspaces", headers=_hdr(user)).json()["workspaces"]
        if w["name"] == "C"
    ]
    assert client.request(
        "DELETE", f"/workspaces/{doomed[0]['id']}", headers=_hdr(user)
    ).status_code == 204
    assert client.post("/workspaces", json={"name": "D"}, headers=_hdr(user)).status_code == 201


@requires_db
def test_you_cannot_delete_another_accounts_workspace(monkeypatch):
    """The id is supplied rather than resolved here, so the tenant GUC is not the guard —
    the explicit account check is."""
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    victim = f"victim-{uuid.uuid4().hex[:8]}"
    attacker = f"attacker-{uuid.uuid4().hex[:8]}"
    try:
        victim_ws = client.get("/workspaces/current", headers=_hdr(victim)).json()["id"]
        _set_plan(attacker, entitlements.PLUS)
        # Give the attacker two workspaces, so the "last workspace" rule isn't what saves us.
        client.post("/workspaces", json={"name": "Spare"}, headers=_hdr(attacker))

        r = client.request("DELETE", f"/workspaces/{victim_ws}", headers=_hdr(attacker))
        assert r.status_code == 404
        with SessionLocal() as s:
            assert s.get(Workspace, uuid.UUID(victim_ws)) is not None
    finally:
        with SessionLocal() as s:
            s.query(Account).filter(
                Account.owner_user_id.in_([victim, attacker])
            ).delete(synchronize_session=False)
            s.commit()


# --- entitlement reads follow the account join ---------------------------------------------------


@requires_db
def test_code_export_reads_the_plan_through_the_account(user, monkeypatch):
    """`workspace.plan` is gone; the gate has to join. A silent failure here would either
    paywall everyone or nobody."""
    ws_id = uuid.UUID(client.get("/workspaces/current", headers=_hdr(user)).json()["id"])
    monkeypatch.setattr(deps, "_resolve_workspace_id", lambda request, session: ws_id)

    _set_plan(user, entitlements.FREE)
    assert client.post("/parse", json={"code": "x = 1"}).status_code == 402

    _set_plan(user, entitlements.PLUS)
    assert client.post("/parse", json={"code": "x = 1"}).status_code == 200


# --- the dev/CI carve-out --------------------------------------------------------------------


def test_resolution_touches_no_database_without_an_internal_key(monkeypatch):
    """`start.sh` promises the app runs with no Postgres at all.

    Asserted by making any session use explode: if resolution reaches for the database on this
    path, the test fails rather than passing quietly against a developer's running instance."""
    monkeypatch.setattr(settings, "internal_key", "")

    def explode():
        raise AssertionError("resolution must not open a session without an internal key")

    monkeypatch.setattr(deps, "SessionLocal", explode)

    class _Req:
        headers: dict[str, str] = {}

    assert deps.request_workspace(_Req()) == uuid.UUID(DEV_WORKSPACE_ID)
    assert deps.run_workspace(_Req()) == uuid.UUID(DEV_WORKSPACE_ID)
    assert deps.may_export_code(_Req()) is True
    assert deps.require_code_export(_Req()) is None


@requires_db
def test_the_caps_are_off_without_an_internal_key(monkeypatch):
    """Same carve-out every other gate uses: in dev/CI every request is the shared dev
    workspace, so enforcing there would break local dev and the e2e suite while protecting
    nothing."""
    monkeypatch.setattr(settings, "internal_key", "")
    with SessionLocal() as s:
        dev_account = accounts.account_for_workspace(s, uuid.UUID(DEV_WORKSPACE_ID))
        if dev_account is None:
            pytest.skip("no dev workspace")
        # Well past the free cap of 3.
        assert accounts.project_count(s, dev_account.id) >= 0

    made = []
    try:
        for i in range(5):
            r = client.post("/agents", json={"name": f"Uncapped{i}", "graph": _graph()})
            assert r.status_code == 200, "the project cap must not bite in dev/CI"
            made.append(r.json()["id"])
    finally:
        with SessionLocal() as s:
            s.query(Agent).filter(Agent.id.in_([uuid.UUID(i) for i in made])).delete(
                synchronize_session=False
            )
            s.commit()
