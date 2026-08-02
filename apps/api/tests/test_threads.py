"""Conversation threads belong to a tenant.

LangGraph resumes state by `thread_id` and asks no questions, so the id *is* the authorization
token for the conversation. It used to be minted by the browser and passed straight through:
naming another caller's thread resumed their state, and both parties' messages ended up in one
conversation. These tests pin the fix — see `calypr_api.threads`.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import threads
from calypr_api.config import settings
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


# --- the naming scheme (pure) --------------------------------------------------------------


def test_a_workspace_thread_is_namespaced_by_its_workspace():
    ws = uuid.uuid4()
    assert threads.workspace_thread(ws, "abc").startswith(f"ws:{ws}:")


def test_a_suffix_cannot_escape_its_namespace():
    """The prefix is server-supplied and comes first, so a crafted suffix can only ever extend a
    thread id — never re-address it into someone else's."""
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    hostile = [
        f"../{theirs}/x",
        f":{theirs}:",
        f"x:ws:{theirs}:y",
        "%",  # a LIKE wildcard, since attribution matches on prefix
        "_",
    ]
    for suffix in hostile:
        got = threads.workspace_thread(mine, suffix)
        # The property that matters is how the id *parses*, not which characters survive: the
        # separator is stripped from the suffix, so whoever splits on ":" — attribution, the GC —
        # always reads my workspace out of field 2 and never theirs.
        assert got.split(":")[:2] == ["ws", str(mine)], got
        assert got.count(":") == 2, f"a suffix introduced a separator: {got}"
        # No `%` either. Attribution builds its LIKE pattern from the *prefix* only, so a suffix
        # is data rather than pattern — but a stray wildcard in an id is a trap for whoever
        # writes the next query, and stripping it costs nothing.
        assert "%" not in got


def test_an_empty_or_unusable_suffix_gets_a_fresh_one():
    """An all-punctuation suffix sanitises to "" — which, if allowed, would put every such
    caller in one shared conversation."""
    ws = uuid.uuid4()
    a = threads.workspace_thread(ws, "!!!")
    b = threads.workspace_thread(ws, "!!!")
    assert a != b
    assert threads.workspace_thread(ws, None) != threads.workspace_thread(ws, None)


def test_share_suffixes_are_unguessable():
    """On a public link this value is the only thing separating two strangers, so it has to be a
    credential rather than a convenience — `secrets`, not the browser's `Math.random`."""
    made = {threads.new_share_suffix() for _ in range(200)}
    assert len(made) == 200
    assert all(len(s) >= 20 for s in made)


# --- the property that matters (end to end) --------------------------------------------------


@requires_db
def test_one_tenant_cannot_resume_another_tenants_thread(monkeypatch):
    """The regression this whole module exists for.

    Before the fix, POSTing another account's `thread_id` loaded their conversation into your
    run — verified by both parties' messages landing in a single thread's state. Now the id the
    caller sends is only a suffix inside their own workspace's namespace, so the two runs cannot
    land in the same thread however hard the caller tries."""
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    graph = input_agent_output(model="fake").model_dump(mode="json")
    shared_suffix = f"collide-{uuid.uuid4().hex}"
    victim = f"victim-{uuid.uuid4().hex[:8]}"
    attacker = f"attacker-{uuid.uuid4().hex[:8]}"

    def _hdr(user: str) -> dict[str, str]:
        return {"x-calypr-internal-key": INTERNAL_KEY, "x-calypr-user-id": user}

    def _run(user: str, message: str) -> None:
        r = client.post(
            "/runs",
            json={"graph": graph, "message": message, "thread_id": shared_suffix},
            headers=_hdr(user),
        )
        assert r.status_code == 200

    try:
        _run(victim, "MY BANK PIN IS 4417")
        _run(attacker, "what did I say?")

        # Asserted on the thread ids the two runs were metered under, not on checkpoint rows:
        # `TestClient` used without a context manager skips the lifespan, so the durable
        # Postgres checkpointer is never installed and nothing lands in `checkpoints`. The ids
        # are the property anyway — the checkpointer keys on exactly this string, so two
        # distinct ids cannot share state however the saver is configured.
        with SessionLocal() as s:
            rows = s.execute(
                text(
                    "SELECT r.thread_id, w.id FROM run r"
                    " JOIN workspace w ON w.id = r.workspace_id"
                    " JOIN account a ON a.id = w.account_id"
                    " WHERE a.owner_user_id IN (:v, :a) AND r.thread_id LIKE :pat"
                ),
                {"v": victim, "a": attacker, "pat": f"%{shared_suffix}"},
            ).all()

        assert len(rows) == 2, f"both runs should be metered, got {rows}"
        thread_ids = {r[0] for r in rows}
        assert len(thread_ids) == 2, f"both callers landed in one thread: {thread_ids}"
        # Each id names its own caller's workspace, so neither can address the other's.
        for thread_id, workspace_id in rows:
            assert thread_id == threads.workspace_thread(workspace_id, shared_suffix)
    finally:
        with SessionLocal() as s:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                s.execute(
                    text(f"DELETE FROM {table} WHERE thread_id LIKE :pat"),  # noqa: S608
                    {"pat": f"%{shared_suffix}"},
                )
            s.execute(
                text("DELETE FROM account WHERE owner_user_id IN (:a, :b)"),
                {"a": victim, "b": attacker},
            )
            s.commit()


@requires_db
def test_a_run_is_metered_for_a_brand_new_user(monkeypatch):
    """Tenant resolution has to *commit* its find-or-create.

    `/runs` never writes through that session, so without a commit the workspace was rolled back
    and the id handed to `RunRecorder` named a row that did not exist. The insert failed its
    foreign key, metering logged itself disabled, and the run streamed unmetered and undebited —
    a new user's first runs were free, silently."""
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    user = f"fresh-{uuid.uuid4().hex[:8]}"
    suffix = f"meter-{uuid.uuid4().hex}"
    try:
        r = client.post(
            "/runs",
            json={
                "graph": input_agent_output(model="fake").model_dump(mode="json"),
                "message": "hello",
                "thread_id": suffix,
            },
            headers={"x-calypr-internal-key": INTERNAL_KEY, "x-calypr-user-id": user},
        )
        assert r.status_code == 200

        with SessionLocal() as s:
            metered = s.execute(
                text(
                    "SELECT count(*) FROM run r JOIN workspace w ON w.id = r.workspace_id"
                    " JOIN account a ON a.id = w.account_id"
                    " WHERE a.owner_user_id = :u AND r.thread_id LIKE :pat"
                ),
                {"u": user, "pat": f"%{suffix}"},
            ).scalar_one()
        assert metered == 1, "the run was not metered — resolution did not persist its workspace"
    finally:
        with SessionLocal() as s:
            for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                s.execute(
                    text(f"DELETE FROM {table} WHERE thread_id LIKE :pat"),  # noqa: S608
                    {"pat": f"%{suffix}"},
                )
            s.execute(text("DELETE FROM account WHERE owner_user_id = :u"), {"u": user})
            s.commit()
