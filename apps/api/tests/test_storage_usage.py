"""Storage measurement and the checkpoint GC that actually bounds it."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from calypr_api import entitlements, storage_usage
from calypr_api.config import settings
from calypr_api.db.models import Account, Agent, Run, Upload
from calypr_api.db.session import SessionLocal, engine
from calypr_api.main import app
from calypr_compiler.golden import input_agent_output
from fastapi.testclient import TestClient
from sqlalchemy import text

client = TestClient(app)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


def _write_checkpoint(session, thread_id: str, blob: bytes | None = None) -> None:
    """Fake a LangGraph checkpoint. These tables are owned by `AsyncPostgresSaver`, not Alembic,
    so the test writes the shape the saver would rather than going through it.

    Random bytes, not a repeated filler: `pg_column_size` reports the *compressed* on-disk size —
    which is the right thing for a storage figure — so `b"x" * 4096` measures as almost zero and
    would make this test pass even if checkpoints weren't counted at all."""
    blob = os.urandom(4096) if blob is None else blob
    cid = str(uuid.uuid4())
    session.execute(
        text(
            "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, type,"
            " checkpoint, metadata) VALUES (:t, '', :c, 'test', '{}'::jsonb, '{}'::jsonb)"
        ),
        {"t": thread_id, "c": cid},
    )
    session.execute(
        text(
            "INSERT INTO checkpoint_blobs (thread_id, checkpoint_ns, channel, version, type,"
            " blob) VALUES (:t, '', 'messages', '1', 'test', :b)"
        ),
        {"t": thread_id, "b": blob},
    )


@pytest.fixture
def tenant(tenant_factory):
    return tenant_factory(entitlements.PLUS)


@requires_db
def test_measurement_counts_graphs_uploads_and_checkpoints(tenant):
    """All three of the visible sources, so a regression in any one shows up as a smaller
    number rather than silently zero."""
    thread = f"thread-{uuid.uuid4().hex}"
    with SessionLocal() as s:
        baseline = storage_usage.measure_account(s, tenant.account_id)

        s.add(
            Agent(
                workspace_id=tenant.workspace_id,
                name="Measured",
                graph_spec=input_agent_output(model="fake").model_dump(mode="json"),
            )
        )
        s.add(
            Upload(
                workspace_id=tenant.workspace_id,
                blob_url="https://blob.example/x.png",
                pathname="uploads/x.png",
                bytes=100_000,
                content_type="image/png",
            )
        )
        s.add(
            Run(
                workspace_id=tenant.workspace_id,
                thread_id=thread,
                status="completed",
                source="playground",
            )
        )
        _write_checkpoint(s, thread)
        s.commit()

        total = storage_usage.measure_account(s, tenant.account_id)

    # The upload is 100 KB and the (incompressible) checkpoint blob 4 KB. The graph's
    # contribution is left loose — its exact JSONB size is not the point and would be brittle.
    assert total >= baseline + 100_000 + 4_096
    assert total > baseline


@requires_db
def test_measure_all_stamps_the_time_it_was_taken(tenant):
    """`storage_measured_at` is what lets the UI say "as of…" instead of implying it's live."""
    before = datetime.now(UTC)
    with SessionLocal() as s:
        storage_usage.measure_all(s)
        acct = s.get(Account, tenant.account_id)
        assert acct.storage_measured_at is not None
        assert acct.storage_measured_at >= before - timedelta(seconds=5)


@requires_db
def test_the_gc_reclaims_expired_state_but_keeps_recent_state(tenant_factory):
    """The retention window is the mechanism that bounds storage, so it has to cut in the right
    place: a thread past the plan's TTL goes, one inside it stays."""
    tenant = tenant_factory(entitlements.FREE)  # 7-day TTL
    old_thread = f"old-{uuid.uuid4().hex}"
    new_thread = f"new-{uuid.uuid4().hex}"

    with SessionLocal() as s:
        for thread, age_days in ((old_thread, 30), (new_thread, 1)):
            s.add(
                Run(
                    workspace_id=tenant.workspace_id,
                    thread_id=thread,
                    status="completed",
                    source="playground",
                )
            )
            s.flush()
            s.execute(
                text("UPDATE run SET created_at = now() - make_interval(days => :d)"
                     " WHERE thread_id = :t"),
                {"d": age_days, "t": thread},
            )
            _write_checkpoint(s, thread)
        s.commit()

        storage_usage.gc_checkpoints(s)

        remaining = {
            row[0]
            for row in s.execute(
                text("SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id = ANY(:t)"),
                {"t": [old_thread, new_thread]},
            ).all()
        }
    assert remaining == {new_thread}, "the expired thread is collected, the recent one is not"


@requires_db
def test_the_gc_is_idempotent_and_does_not_rescan_swept_threads(tenant_factory):
    """`run` rows outlive their checkpoints, so without an existence check every already-swept
    thread would match forever, fill the batch, and starve the threads that need collecting."""
    tenant = tenant_factory(entitlements.FREE)
    thread = f"sweep-{uuid.uuid4().hex}"
    with SessionLocal() as s:
        s.add(
            Run(
                workspace_id=tenant.workspace_id,
                thread_id=thread,
                status="completed",
                source="playground",
            )
        )
        s.flush()
        s.execute(
            text("UPDATE run SET created_at = now() - interval '30 days' WHERE thread_id = :t"),
            {"t": thread},
        )
        _write_checkpoint(s, thread)
        s.commit()

        first = storage_usage.gc_checkpoints(s)
        assert first["rows"] > 0

        second = storage_usage.gc_checkpoints(s)
        assert second["rows"] == 0
        # The run row is still there — history is kept, only the state is reclaimed.
        assert s.execute(
            text("SELECT count(*) FROM run WHERE thread_id = :t"), {"t": thread}
        ).scalar_one() == 1


# --- the endpoints fail closed -------------------------------------------------------------


def test_internal_endpoints_refuse_without_a_key(monkeypatch):
    """The opposite carve-out from every other gate, deliberately: these delete data, so an
    unconfigured deployment must not expose them."""
    monkeypatch.setattr(settings, "internal_key", "")
    assert client.post("/internal/gc/checkpoints").status_code == 503
    assert client.post("/internal/gc/measure-storage").status_code == 503


def test_internal_endpoints_refuse_a_wrong_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_key", "right")
    assert client.post(
        "/internal/gc/checkpoints", headers={"x-calypr-internal-key": "wrong"}
    ).status_code == 401
    assert client.post("/internal/gc/checkpoints").status_code == 401


@requires_db
def test_measurement_counts_generated_media(tenant):
    """Generated media bills exactly like an upload, so it has to reach the storage figure —
    and it is the larger of the two: one image run writes megabytes."""
    from calypr_api.db.models import Asset

    with SessionLocal() as s:
        baseline = storage_usage.measure_account(s, tenant.account_id)
        s.add(
            Asset(
                workspace_id=tenant.workspace_id,
                kind="image",
                blob_url="https://blob.example/runs/png/counted.png",
                bytes=3_000_000,
                caption="a fox",
            )
        )
        s.commit()
        assert storage_usage.measure_account(s, tenant.account_id) - baseline == 3_000_000


@requires_db
def test_an_actively_used_thread_survives_its_oldest_run(tenant_factory):
    """The TTL means "untouched for N days", and only the most recent run can say that.

    This was a real bug: the query matched on `DISTINCT r.thread_id … WHERE r.created_at <
    cutoff`, so a conversation used daily was collected on the strength of the run that started
    it three weeks ago. Invisible while nothing could reopen an old thread — the History tab
    invites exactly that, and the symptom is an agent that has forgotten a chat the user was in
    the middle of."""
    tenant = tenant_factory(entitlements.FREE)  # 7-day TTL
    thread = f"busy-{uuid.uuid4().hex}"

    with SessionLocal() as s:
        for age_days in (30, 1):  # started a month ago, used yesterday
            s.add(
                Run(
                    workspace_id=tenant.workspace_id,
                    thread_id=thread,
                    status="completed",
                    source="playground",
                )
            )
            s.flush()
            s.execute(
                text(
                    "UPDATE run SET created_at = now() - make_interval(days => :d)"
                    " WHERE thread_id = :t AND created_at > now() - interval '1 minute'"
                ),
                {"d": age_days, "t": thread},
            )
        _write_checkpoint(s, thread)
        s.commit()

        storage_usage.gc_checkpoints(s)

        left = s.execute(
            text("SELECT count(*) FROM checkpoints WHERE thread_id = :t"), {"t": thread}
        ).scalar_one()
    assert left == 1, "a thread used yesterday was collected because it started a month ago"


@requires_db
def test_orphan_blob_gc_retries_and_gives_up(tenant_factory, monkeypatch):
    """The parking lot `history.py` writes into when a live blob delete fails. Successes drop
    their row; repeated failures stop being retried but stay as the audit trail."""
    from calypr_api.db.models import OrphanBlob

    t = tenant_factory()
    with SessionLocal() as s:
        s.add_all(
            [
                OrphanBlob(workspace_id=t.workspace_id, blob_url="https://blob.example/ok.png"),
                OrphanBlob(workspace_id=t.workspace_id, blob_url="https://blob.example/bad.png"),
            ]
        )
        s.commit()

    from calypr_storage import BlobError

    async def flaky(urls):
        if any("bad" in u for u in urls):
            raise BlobError("still refusing")

    monkeypatch.setattr(storage_usage, "delete_blob", flaky)

    with SessionLocal() as s:
        result = storage_usage.gc_orphan_blobs(s)
        assert result == {"deleted": 1, "failed": 1, "considered": 2}
        rows = s.query(OrphanBlob).filter(OrphanBlob.workspace_id == t.workspace_id).all()
        assert [r.blob_url for r in rows] == ["https://blob.example/bad.png"]
        assert rows[0].attempts == 1

        # Keep failing and it eventually stops being considered at all.
        for _ in range(storage_usage.MAX_ORPHAN_ATTEMPTS):
            storage_usage.gc_orphan_blobs(s)
        assert storage_usage.gc_orphan_blobs(s)["considered"] == 0
        # …but the row survives, so an operator can still find the leak.
        assert s.query(OrphanBlob).filter(OrphanBlob.workspace_id == t.workspace_id).count() == 1
