"""RunRecorder + `/runs`/`/assist` metering (WEEK2 plan §B gates).

Two tiers:
- **DB-less** (always run): the recorder self-disables when the DB is unreachable, and the
  stream still delivers tokens + [DONE]. This is start.sh's DB-less promise.
- **DB-backed** (skipped without Postgres, run in CI): rows are written with the right
  node_id/model/tokens/cost, `/assist` records source="assist", and RLS is in place.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import metering
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.session import SessionLocal, engine, set_tenant
from calypr_api.main import app
from calypr_api.metering import RunRecorder
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


def _boom() -> None:
    raise RuntimeError("db down")


# --------------------------------------------------------------------------- DB-less


def test_recorder_disables_and_is_noop_when_db_down(monkeypatch):
    monkeypatch.setattr(metering, "SessionLocal", _boom)
    rec = RunRecorder.start(uuid.UUID(DEV_WORKSPACE_ID), source="playground")
    assert rec._enabled is False
    # Every method must be a safe no-op — no exception escapes onto the hot path.
    rec.add_usage({"node_id": "agent", "model": "fake", "input_tokens": 3, "output_tokens": 5})
    rec.finish("completed")
    rec.fail()


def test_runs_streams_tokens_and_done_with_db_down(monkeypatch):
    """The core guardrail: Postgres down ⇒ `/runs` still streams tokens + [DONE], no error."""
    monkeypatch.setattr(metering, "SessionLocal", _boom)
    graph = input_agent_output(model="fake").model_dump()
    r = client.post("/runs", json={"graph": graph, "message": "hello world"})
    assert r.status_code == 200
    body = r.text
    assert "Echo:" in body  # tokens streamed
    assert "[DONE]" in body
    assert '"type": "error"' not in body  # metering failure never surfaces to the client


# --------------------------------------------------------------------------- DB-backed

pytest_db = pytest.mark.skipif(not _db_available(), reason="Postgres not available")


@pytest_db
def test_fake_run_writes_run_and_usage_rows():
    from calypr_api.db.models import Run, RunUsage
    from sqlalchemy import select

    thread = f"meter-{uuid.uuid4()}"
    graph = input_agent_output(model="fake").model_dump()
    r = client.post("/runs", json={"graph": graph, "message": "hi there", "thread_id": thread})
    assert r.status_code == 200 and "[DONE]" in r.text

    with SessionLocal() as s:
        set_tenant(s, DEV_WORKSPACE_ID)
        run = s.execute(select(Run).where(Run.thread_id == thread)).scalar_one()
        assert run.status == "completed"
        assert run.source == "playground"
        assert run.finished_at is not None

        usages = s.execute(select(RunUsage).where(RunUsage.run_id == run.id)).scalars().all()
        assert usages, "expected usage rows"
        assert all(u.node_id == "agent" for u in usages)
        assert all(u.model == "fake" for u in usages)
        assert run.input_tokens == sum(u.input_tokens for u in usages)
        assert run.output_tokens == sum(u.output_tokens for u in usages)
        assert float(run.cost_usd) == 0.0  # the fake model is free


@pytest_db
def test_recorder_persists_computed_cost():
    """Cost arithmetic reaches the `run` row: 1M in + 1M out on gpt-4.1-mini = $2.00."""
    from calypr_api.db.models import Run
    from sqlalchemy import select

    rec = RunRecorder.start(uuid.UUID(DEV_WORKSPACE_ID), source="api")
    assert rec._enabled
    rec.add_usage(
        {
            "node_id": "n1",
            "model": "gpt-4.1-mini",
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
        }
    )
    rec.finish("completed")

    with SessionLocal() as s:
        set_tenant(s, DEV_WORKSPACE_ID)
        run = s.execute(select(Run).where(Run.id == rec._run_id)).scalar_one()
        assert float(run.cost_usd) == pytest.approx(2.00)
        assert run.input_tokens == 1_000_000
        assert run.output_tokens == 1_000_000


@pytest_db
def test_assist_writes_run_with_source_assist():
    from calypr_api.db.models import Run
    from sqlalchemy import select

    # Keyless fake path (no internal key) → dev workspace, FakeAssistant, real usage event.
    r = client.post("/assist", json={"messages": [{"role": "user", "content": "make a chatbot"}]})
    assert r.status_code == 200
    frames = [f for f in r.text.split("\n\n") if '"type": "usage"' in f]
    assert frames, "assist should stream a usage event"

    with SessionLocal() as s:
        set_tenant(s, DEV_WORKSPACE_ID)
        run = (
            s.execute(select(Run).where(Run.source == "assist").order_by(Run.created_at.desc()))
            .scalars()
            .first()
        )
        assert run is not None
        assert run.status == "completed"


@pytest_db
def test_run_tables_have_rls_enabled():
    """Both metering tables carry RLS + a tenant policy (defense-in-depth; enforcement is
    forced on the app role in a later hardening step — WEEK2 plan §1)."""
    with engine.connect() as conn:
        for table in ("run", "run_usage"):
            rls_on = conn.execute(
                text("SELECT relrowsecurity FROM pg_class WHERE relname = :t"),
                {"t": table},
            ).scalar()
            assert rls_on is True, f"{table} missing RLS"
            policies = conn.execute(
                text("SELECT count(*) FROM pg_policies WHERE tablename = :t"),
                {"t": table},
            ).scalar()
            assert policies >= 1, f"{table} missing policy"
