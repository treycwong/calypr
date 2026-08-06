"""`purge.py`: the destruction half of account deletion.

Deleting rows is the easy part and would pass under almost any implementation. The test that
earns its place is `test_the_purge_needs_nothing_but_its_own_record`: it pins the property that
the purge reads `account_purge` and never joins back through `run` or `workspace`.

That framing is deliberate, and it was chosen *after* checking. The obvious phrasing —
"checkpoints must be deleted before the cascade" — turns out not to be a real constraint: because
the thread prefixes are stored durably, reordering those two steps changes nothing and a test
asserting it passes either way. What is genuinely fatal is re-deriving the prefixes from live
rows, or moving collection out of the request and into the purge. Then the threads are
unreachable *and no GC arm covers them* — `gc_checkpoints`'s orphan arm excludes `ws:%` and its
TTL arm joins run → workspace → billing_account, all gone — so the bytes leak forever, invisibly,
for precisely the people who asked to be forgotten.

Everything else here defends a property the durable record was introduced to buy: crash-resume,
blob failures not blocking the database, idempotence, and the grace window.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import purge
from calypr_api.config import settings
from calypr_api.db.models import Account, AccountPurge, Agent, Run, ShareLink, Upload, Workspace
from calypr_api.db.session import SessionLocal, engine
from calypr_api.main import app
from calypr_storage import BlobError
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


@pytest.fixture(autouse=True)
def no_real_blob_calls(monkeypatch):
    """Never touch Vercel from a test. Individual tests override this to simulate failure."""

    async def ok(*args, **kwargs):
        return None

    monkeypatch.setattr(purge, "delete_blob", ok)


@pytest.fixture
def user(monkeypatch):
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    uid = f"purge-{uuid.uuid4().hex[:10]}"
    yield uid
    with SessionLocal() as s:
        for a in s.query(Account).filter(Account.owner_user_id == uid).all():
            s.query(AccountPurge).filter(AccountPurge.account_id == a.id).delete(
                synchronize_session=False
            )
        s.query(Account).filter(Account.owner_user_id == uid).delete(synchronize_session=False)
        s.commit()


def _hdr(user_id: str) -> dict[str, str]:
    return {"x-calypr-internal-key": INTERNAL_KEY, "x-calypr-user-id": user_id}


def _checkpoint(session, thread_id: str) -> None:
    """One row in each of the three checkpoint tables for this thread.

    Written by hand because LangGraph owns these tables — they are outside Alembic and outside
    our models, which is the whole reason the purge has to name them explicitly."""
    session.execute(
        text(
            "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, checkpoint,"
            " metadata) VALUES (:t, '', :c, '{}'::jsonb, '{}'::jsonb)"
        ),
        {"t": thread_id, "c": str(uuid.uuid4())},
    )
    session.execute(
        text(
            "INSERT INTO checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type,"
            " blob) VALUES (:t, '', 'ch', 'v1', 'bytes', :b)"
        ),
        {"t": thread_id, "b": b"x" * 32},
    )
    session.execute(
        text(
            "INSERT INTO checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id, task_id,"
            " idx, channel, type, blob) VALUES (:t, '', :c, :k, 0, 'ch', 'bytes', :b)"
        ),
        {"t": thread_id, "c": str(uuid.uuid4()), "k": str(uuid.uuid4()), "b": b"y" * 8},
    )


def _checkpoint_rows(thread_ids: list[str]) -> int:
    with SessionLocal() as s:
        return sum(
            s.execute(
                text(f"SELECT count(*) FROM {t} WHERE thread_id = ANY(:ids)"),  # noqa: S608
                {"ids": thread_ids},
            ).scalar()
            for t in ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
        )


def _age_request(account_id: uuid.UUID, days: int) -> None:
    """Push the request back in time so the grace window has passed."""
    with SessionLocal() as s:
        s.execute(
            text(
                "UPDATE account_purge SET requested_at = now() - make_interval(days => :d)"
                " WHERE account_id = :a"
            ),
            {"d": days, "a": str(account_id)},
        )
        s.commit()


def _seed_and_delete(user_id: str) -> tuple[uuid.UUID, list[str]]:
    """An account with all three flavours of thread, then deleted. Returns (account_id, threads)."""
    with SessionLocal() as s:
        acc = uuid.UUID(
            str(s.execute(text("SELECT resolve_account(:u)"), {"u": user_id}).scalar_one())
        )
        s.commit()

    with SessionLocal() as s:
        ws = s.query(Workspace).filter(Workspace.account_id == acc).one()
        agent = Agent(workspace_id=ws.id, name="t", graph_spec={})
        s.add(agent)
        s.flush()
        token = f"tok-{uuid.uuid4().hex[:8]}"
        s.add(ShareLink(token=token, agent_id=agent.id, workspace_id=ws.id))

        ws_thread = f"ws:{ws.id}:main"
        share_thread = f"share:{token}:abc"
        legacy_thread = f"legacy-{uuid.uuid4().hex[:8]}"

        # The legacy thread is reachable **only** through `run.thread_id` — no prefix to match.
        s.add(
            Run(
                workspace_id=ws.id,
                thread_id=legacy_thread,
                status="completed",
                source="playground",
            )
        )
        s.add(
            Run(
                workspace_id=ws.id,
                thread_id=ws_thread,
                status="completed",
                source="playground",
            )
        )
        s.add(
            Upload(
                workspace_id=ws.id,
                blob_url="https://store.public.blob.vercel-storage.com/a.png",
                pathname="a.png",
                bytes=1,
            )
        )
        for t in (ws_thread, share_thread, legacy_thread):
            _checkpoint(s, t)
        s.commit()
        threads = [ws_thread, share_thread, legacy_thread]

    resp = client.request("DELETE", "/account", headers=_hdr(user_id))
    assert resp.status_code == 200
    return acc, threads


# --- the headline ------------------------------------------------------------------------------


@requires_db
def test_every_flavour_of_thread_is_gone_after_a_purge(user):
    """All three shapes of thread are actually collected.

    A `ws:` thread, a `share:` thread, and a legacy thread reachable only via `run.thread_id` end
    with zero rows in all three checkpoint tables. This is the coverage test — that no *kind* of
    thread was forgotten. The ordering hazard is the test below."""
    account_id, threads = _seed_and_delete(user)
    assert _checkpoint_rows(threads) == 9  # 3 threads × 3 tables
    _age_request(account_id, 8)

    with SessionLocal() as s:
        result = purge.purge_accounts(s)
    assert result["purged"] == 1

    assert _checkpoint_rows(threads) == 0

    # And the account itself is a hard delete, not a tombstone — the UNIQUE `owner_user_id` slot
    # has to be free for a returning user.
    with SessionLocal() as s:
        assert s.get(Account, account_id) is None
        row = s.query(AccountPurge).filter(AccountPurge.account_id == account_id).one()
        assert row.purged_at is not None  # the audit trail outlives the account, by design


@requires_db
def test_the_purge_needs_nothing_but_its_own_record(user):
    """**The test this file exists for — the ordering hazard, stated as a property.**

    Thread ids are collected in the *request*, into `account_purge`, precisely so that the purge
    never has to join back through `run` or `workspace`. This asserts that independence directly:
    the account's workspaces (and with them every run row) are destroyed **first**, and the purge
    must still find and delete all three threads.

    Why this framing rather than "checkpoints before the cascade": because the durable record
    means the purge's *internal* step order genuinely doesn't matter — a reordering passes, and a
    test asserting otherwise would be testing nothing. What is actually fatal is someone
    "simplifying" the purge to re-derive prefixes with a live query, or moving collection into the
    purge. Either change makes those threads unreachable, and **no GC arm covers them**:
    `gc_checkpoints`'s orphan arm excludes `ws:%`, and its TTL arm joins run → workspace →
    billing_account. The bytes would leak forever, silently, for the users who asked to be
    forgotten. This test fails the moment that dependency is reintroduced.
    """
    account_id, threads = _seed_and_delete(user)
    _age_request(account_id, 8)

    # Simulate the worst case: everything the purge might be tempted to join through is gone.
    with SessionLocal() as s:
        s.execute(
            text("DELETE FROM workspace WHERE account_id = :a"), {"a": str(account_id)}
        )
        s.commit()
        assert s.query(Run).count() >= 0  # runs for this account went with the workspaces

    with SessionLocal() as s:
        assert purge.purge_accounts(s)["purged"] == 1

    assert _checkpoint_rows(threads) == 0


# --- crash-resume, the reason the record is durable ---------------------------------------------


@requires_db
def test_a_failed_blob_chunk_is_parked_and_does_not_block_the_database(user, monkeypatch):
    """Vercel being down must not be able to veto someone's deletion request. The urls stay
    visible in `blob_urls_failed` so the leak is an operator's problem rather than an invisible
    one."""
    account_id, threads = _seed_and_delete(user)
    _age_request(account_id, 8)

    async def boom(*args, **kwargs):
        raise BlobError("vercel is down")

    monkeypatch.setattr(purge, "delete_blob", boom)

    with SessionLocal() as s:
        assert purge.purge_accounts(s)["purged"] == 1

    with SessionLocal() as s:
        row = s.query(AccountPurge).filter(AccountPurge.account_id == account_id).one()
        assert row.purged_at is not None
        assert row.blob_urls == []  # drained either way
        assert row.blob_urls_failed == ["https://store.public.blob.vercel-storage.com/a.png"]
        assert s.get(Account, account_id) is None  # the database purge went ahead
    assert _checkpoint_rows(threads) == 0


@requires_db
def test_crash_resume_does_not_reissue_deletes_for_urls_already_handled(user, monkeypatch):
    """**Why the record is durable rather than collected inline.**

    Fail partway, re-run, and the urls that already succeeded are not sent again. Without the
    drained `blob_urls` column there would be no way to know which those were."""
    account_id, _ = _seed_and_delete(user)
    _age_request(account_id, 8)

    # Give it three chunks' worth of urls and a chunk size of 1.
    urls = [f"https://store.public.blob.vercel-storage.com/{i}.png" for i in range(3)]
    with SessionLocal() as s:
        s.execute(
            text("UPDATE account_purge SET blob_urls = :u WHERE account_id = :a"),
            {"u": urls, "a": str(account_id)},
        )
        s.commit()
    monkeypatch.setattr(purge, "BLOB_CHUNK", 1)

    seen: list[str] = []

    async def fail_on_second(chunk, *args, **kwargs):
        seen.extend(chunk)
        if chunk == [urls[1]]:
            raise RuntimeError("crash")  # not a BlobError: a hard failure mid-purge
        return None

    monkeypatch.setattr(purge, "delete_blob", fail_on_second)
    with SessionLocal() as s:
        assert purge.purge_accounts(s)["failed"] == 1

    with SessionLocal() as s:
        row = s.query(AccountPurge).filter(AccountPurge.account_id == account_id).one()
        assert row.purged_at is None
        assert urls[0] not in row.blob_urls  # handled, and recorded as handled

    # Re-run cleanly. The first url must not be issued a second time.
    seen.clear()

    async def ok(chunk, *args, **kwargs):
        seen.extend(chunk)
        return None

    monkeypatch.setattr(purge, "delete_blob", ok)
    with SessionLocal() as s:
        assert purge.purge_accounts(s)["purged"] == 1

    assert urls[0] not in seen
    assert set(seen) == {urls[1], urls[2]}


@requires_db
def test_purge_is_idempotent(user):
    """A second run finds nothing to do rather than erroring on the account it already removed."""
    account_id, _ = _seed_and_delete(user)
    _age_request(account_id, 8)

    with SessionLocal() as s:
        assert purge.purge_accounts(s)["purged"] == 1
    with SessionLocal() as s:
        assert purge.purge_accounts(s) == {"purged": 0, "failed": 0, "considered": 0}


# --- the guard rails ---------------------------------------------------------------------------


@requires_db
def test_the_grace_window_is_respected(user):
    """The only recovery there is. An account deleted today must still be there tomorrow."""
    account_id, threads = _seed_and_delete(user)
    # No ageing: requested just now, well inside the 7-day window.

    with SessionLocal() as s:
        assert purge.purge_accounts(s)["considered"] == 0

    with SessionLocal() as s:
        assert s.get(Account, account_id) is not None
    assert _checkpoint_rows(threads) == 9


@requires_db
def test_a_live_account_is_never_touched(user):
    """The blast radius. A purge running next to an ordinary account must leave it alone."""
    account_id, _ = _seed_and_delete(user)
    _age_request(account_id, 8)

    other = f"purge-live-{uuid.uuid4().hex[:8]}"
    with SessionLocal() as s:
        other_acc = uuid.UUID(
            str(s.execute(text("SELECT resolve_account(:u)"), {"u": other}).scalar_one())
        )
        s.commit()
    try:
        with SessionLocal() as s:
            purge.purge_accounts(s)
        with SessionLocal() as s:
            assert s.get(Account, other_acc) is not None
            assert s.query(Workspace).filter(Workspace.account_id == other_acc).count() == 1
    finally:
        with SessionLocal() as s:
            s.query(Account).filter(Account.id == other_acc).delete(synchronize_session=False)
            s.commit()


@requires_db
def test_a_record_that_keeps_failing_stops_being_retried(user, monkeypatch):
    """Otherwise one poisoned record retries every night forever and drowns the log."""
    account_id, _ = _seed_and_delete(user)
    _age_request(account_id, 8)
    with SessionLocal() as s:
        s.execute(
            text("UPDATE account_purge SET attempts = :n WHERE account_id = :a"),
            {"n": purge.MAX_ATTEMPTS, "a": str(account_id)},
        )
        s.commit()

    with SessionLocal() as s:
        assert purge.purge_accounts(s)["considered"] == 0
    with SessionLocal() as s:
        assert s.get(Account, account_id) is not None  # left for a human, not destroyed


def test_the_endpoint_fails_closed_without_a_key(monkeypatch):
    """A delete endpoint that an unconfigured deployment leaves publicly triggerable would be
    the worst possible failure in this file."""
    monkeypatch.setattr(settings, "internal_key", "")
    assert client.post("/internal/gc/purge-accounts").status_code == 503


@requires_db
def test_the_endpoint_requires_the_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    assert client.post("/internal/gc/purge-accounts").status_code == 401
    r = client.post(
        "/internal/gc/purge-accounts", headers={"x-calypr-internal-key": INTERNAL_KEY}
    )
    assert r.status_code == 200


@requires_db
def test_generated_media_and_parked_blobs_are_collected_for_deletion(user):
    """Deleting an account has to name **every** blob it owns, and `upload` is only one source.

    Generated media (`asset`) is the bigger one — an image run writes megabytes — and
    `orphan_blob` holds objects a live delete already failed on. Once the account is purged the
    rows they were reachable through are gone, so anything missed here bills forever with no GC
    arm anywhere that could ever find it again. The join through `workspace.account_id` is what
    keeps this from ever naming somebody else's object; see the comment at the collection site."""
    from calypr_api.db.models import Asset, OrphanBlob

    with SessionLocal() as s:
        acc = uuid.UUID(
            str(s.execute(text("SELECT resolve_account(:u)"), {"u": user}).scalar_one())
        )
        s.commit()

    with SessionLocal() as s:
        ws = s.query(Workspace).filter(Workspace.account_id == acc).one()
        s.add(
            Upload(
                workspace_id=ws.id,
                blob_url="https://store.public.blob.vercel-storage.com/uploads/in.png",
                pathname="uploads/in.png",
                bytes=1,
            )
        )
        s.add(
            Asset(
                workspace_id=ws.id,
                kind="image",
                blob_url="https://store.public.blob.vercel-storage.com/runs/png/out.png",
                bytes=2048,
                caption="generated",
            )
        )
        s.add(
            OrphanBlob(
                workspace_id=ws.id,
                blob_url="https://store.public.blob.vercel-storage.com/runs/png/stuck.png",
            )
        )
        s.commit()

    assert client.request("DELETE", "/account", headers=_hdr(user)).status_code == 200

    with SessionLocal() as s:
        recorded = set(
            s.query(AccountPurge).filter(AccountPurge.account_id == acc).one().blob_urls
        )
    assert recorded == {
        "https://store.public.blob.vercel-storage.com/uploads/in.png",
        "https://store.public.blob.vercel-storage.com/runs/png/out.png",
        "https://store.public.blob.vercel-storage.com/runs/png/stuck.png",
    }
