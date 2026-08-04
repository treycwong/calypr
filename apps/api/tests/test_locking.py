"""Locking the capacity a downgraded account no longer has.

Caps were only ever enforced at create time, so a lapsed Plus account kept three workspaces and
twenty projects and could go on working in all of them forever. These lock the excess instead.

The governing rule, same as the rest of the downgrade path: **take back capacity, never data.**
So the tests that matter most are the ones asserting what a lock does *not* do — it deletes
nothing, it never blocks a read, and it never blocks the delete that is the way back under the
cap. A lock that blocks its own remedy is a trap.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import entitlements, locking, run_access
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
        h["x-calypr-workspace-id"] = str(workspace_id)
    return h


@pytest.fixture
def user(monkeypatch):
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    uid = f"lock-{uuid.uuid4().hex[:10]}"
    yield uid
    with SessionLocal() as s:
        s.query(Account).filter(Account.owner_user_id == uid).delete(synchronize_session=False)
        s.commit()


def _plus_account_at_capacity(user_id: str, *, workspaces: int = 3, projects: int = 4):
    """A Plus account with `workspaces` workspaces and `projects` agents in the first one.

    Returns (account_id, [workspace ids oldest-first], [agent ids oldest-first])."""
    with SessionLocal() as s:
        acc = uuid.UUID(
            str(s.execute(text("SELECT resolve_account(:u)"), {"u": user_id}).scalar_one())
        )
        s.get(Account, acc).plan = entitlements.PLUS
        s.commit()

    with SessionLocal() as s:
        first = s.query(Workspace).filter(Workspace.account_id == acc).one()
        s.execute(
            text("UPDATE workspace SET created_at = now() - interval '1 hour' WHERE id = :i"),
            {"i": str(first.id)},
        )
        ws_ids = [first.id]
        for i in range(workspaces - 1):
            w = Workspace(account_id=acc, name=f"extra-{i}")
            s.add(w)
            s.flush()
            # Age them deterministically **into the past**, oldest first, so anything a test
            # adds afterwards is genuinely newer than everything this helper made.
            s.execute(
                text("UPDATE workspace SET created_at = now() - make_interval(secs => :n)"
                     " WHERE id = :i"),
                {"n": workspaces - i - 1, "i": str(w.id)},
            )
            ws_ids.append(w.id)
        agent_ids = []
        for i in range(projects):
            a = Agent(workspace_id=first.id, name=f"p{i}", graph_spec=_graph())
            s.add(a)
            s.flush()
            s.execute(
                text("UPDATE agent SET created_at = now() - make_interval(secs => :n)"
                     " WHERE id = :i"),
                {"n": projects - i, "i": str(a.id)},
            )
            agent_ids.append(a.id)
        s.commit()
    return acc, ws_ids, agent_ids


def _downgrade(account_id: uuid.UUID) -> None:
    with SessionLocal() as s:
        s.get(Account, account_id).plan = entitlements.FREE
        s.commit()


# --- which rows lock -----------------------------------------------------------------------------


@requires_db
def test_the_oldest_survive_and_the_newest_lock(user):
    """Oldest-first, matching how `resolve_workspace` picks a default and how
    `list_account_workspaces` orders — so "your original workspace still works" is what someone
    would guess without being told."""
    acc, ws_ids, agent_ids = _plus_account_at_capacity(user)
    _downgrade(acc)  # Free: 1 workspace, 3 projects

    with SessionLocal() as s:
        locked_ws = locking.locked_workspace_ids(s, acc, entitlements.FREE)
        locked_agents = locking.locked_agent_ids(s, acc, entitlements.FREE)

    assert ws_ids[0] not in locked_ws
    assert set(ws_ids[1:]) == locked_ws
    # Free allows 3 projects, so of four only the newest locks.
    assert set(agent_ids[:3]).isdisjoint(locked_agents)
    assert locked_agents == {agent_ids[3]}


@requires_db
def test_nothing_locks_while_the_plan_still_covers_it(user):
    """The boundary is the cap, not the plan name — so raising `LIMITS` is the only edit needed
    to change this."""
    acc, _, _ = _plus_account_at_capacity(user)
    with SessionLocal() as s:
        assert locking.locked_workspace_ids(s, acc, entitlements.PLUS) == set()
        assert locking.locked_agent_ids(s, acc, entitlements.PLUS) == set()


# --- what a lock refuses, and what it must not --------------------------------------------------


@requires_db
def test_a_locked_workspace_refuses_writes_but_serves_reads(user):
    acc, ws_ids, _ = _plus_account_at_capacity(user)
    _downgrade(acc)
    locked = ws_ids[-1]

    # Reads are always allowed — the point is to stop new work, not to hold data hostage.
    assert client.get("/agents", headers=_hdr(user, locked)).status_code == 200
    assert client.get("/workspaces/current", headers=_hdr(user, locked)).status_code == 200

    # Renaming it is new configuration.
    r = client.patch("/workspaces/current", json={"name": "nope"}, headers=_hdr(user, locked))
    assert r.status_code == 402
    assert r.json()["detail"]["reason"] == "locked"


@requires_db
def test_deleting_is_always_allowed_and_unlocks_the_rest(user):
    """**A lock must never block its own remedy.** Deleting down to the cap is one of the two ways
    out (the other is upgrading), so a lock that refused deletes would be a trap with no exit."""
    acc, ws_ids, _ = _plus_account_at_capacity(user)
    _downgrade(acc)

    # **From inside the locked workspace**, which is how someone actually does this: switch to
    # the one you're giving up, then delete it. Sending these from the unlocked home workspace
    # would pass even if the delete route were gated, and prove nothing.
    for ws in ws_ids[1:]:
        assert client.request(
            "DELETE", f"/workspaces/{ws}", headers=_hdr(user, ws)
        ).status_code == 204

    with SessionLocal() as s:
        assert locking.locked_workspace_ids(s, acc, entitlements.FREE) == set()
    # And the survivor is writable again, with no plan change.
    assert client.patch(
        "/workspaces/current", json={"name": "fine"}, headers=_hdr(user, ws_ids[0])
    ).status_code == 200


@requires_db
def test_a_locked_project_refuses_edits_but_not_reads_or_deletes(user):
    acc, ws_ids, agent_ids = _plus_account_at_capacity(user)
    _downgrade(acc)
    locked_agent = str(agent_ids[-1])
    home = ws_ids[0]

    assert client.get(f"/agents/{locked_agent}", headers=_hdr(user, home)).status_code == 200

    r = client.put(
        f"/agents/{locked_agent}", json={"name": "edited"}, headers=_hdr(user, home)
    )
    assert r.status_code == 402
    assert r.json()["detail"]["kind"] == "project"

    # Sharing is publishing new work from it, so it follows the same lock.
    assert client.post(
        f"/agents/{locked_agent}/share", json={}, headers=_hdr(user, home)
    ).status_code == 402

    # But it can still be deleted — the way back under the cap.
    assert client.request(
        "DELETE", f"/agents/{locked_agent}", headers=_hdr(user, home)
    ).status_code == 204


@requires_db
def test_an_unlocked_project_in_a_locked_workspace_is_still_locked(user):
    """A project inside a read-only workspace is unreachable for new work whatever its own rank —
    checking only the project would leave a writable island in a locked workspace."""
    acc, ws_ids, _ = _plus_account_at_capacity(user)
    locked_ws = ws_ids[-1]
    with SessionLocal() as s:
        a = Agent(workspace_id=locked_ws, name="only one here", graph_spec=_graph())
        s.add(a)
        s.commit()
        agent_id = a.id
    _downgrade(acc)

    with SessionLocal() as s:
        # It is the account's 5th project, so it is over the Free cap too — pin the workspace
        # reason specifically by asserting the payload names the workspace.
        assert agent_id in locking.locked_agent_ids(s, acc, entitlements.FREE)

    r = client.put(f"/agents/{agent_id}", json={"name": "x"}, headers=_hdr(user, locked_ws))
    assert r.status_code == 402
    assert r.json()["detail"]["kind"] == "workspace"


# --- runs ----------------------------------------------------------------------------------------


@requires_db
def test_runs_are_refused_in_a_locked_workspace(user):
    """Running is new work: it burns credits and writes run rows. Refused before the credit check,
    because "you're out of credits" would send someone to wait for a monthly reset that cannot
    fix a lapsed subscription."""
    acc, ws_ids, _ = _plus_account_at_capacity(user)
    _downgrade(acc)

    from calypr_dsl import GraphSpec

    graph = GraphSpec.model_validate(_graph())
    gate = run_access.check_run_gates(ws_ids[-1], graph)
    assert gate is not None
    code, message = gate
    assert code == "workspace_locked"
    assert "read-only" in message

    # The survivor still runs.
    assert run_access.check_run_gates(ws_ids[0], graph) is None


# --- the carve-outs ------------------------------------------------------------------------------


@requires_db
def test_nothing_locks_without_an_internal_key(monkeypatch, user):
    """Dev/CI. Every request is the shared dev workspace there, so enforcing would break local dev
    and the e2e suite while protecting nothing."""
    acc, ws_ids, agent_ids = _plus_account_at_capacity(user)
    _downgrade(acc)
    monkeypatch.setattr(settings, "internal_key", "")

    from calypr_dsl import GraphSpec

    assert run_access.check_run_gates(ws_ids[-1], GraphSpec.model_validate(_graph())) is None
    assert locking.locked_run_message(ws_ids[-1]) is None


@requires_db
def test_the_dev_workspace_is_never_locked(monkeypatch):
    """Anonymous production traffic lands there; locking it would break every visitor at once."""
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    assert locking.locked_run_message(uuid.UUID(DEV_WORKSPACE_ID)) is None


@requires_db
def test_the_lock_check_fails_open(monkeypatch, user):
    """Consistent with every other gate on the run path: a database hiccup must not stop people
    working. Being wrong costs one run in a workspace that should have been read-only; failing
    closed costs an outage that looks like a billing problem."""
    acc, ws_ids, _ = _plus_account_at_capacity(user)
    _downgrade(acc)

    def boom(*args, **kwargs):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr(locking.accounts, "account_for_workspace", boom)
    assert locking.locked_run_message(ws_ids[-1]) is None
