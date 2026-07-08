"""Platform spend kill-switch (WEEK2 plan §C4 gates): disabled by default, trips at the
boundary, fails open when the DB is down, and refuses runs/assists via an SSE error."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from calypr_api import spend
from calypr_api.config import settings
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.session import SessionLocal, engine, set_tenant
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


@pytest.fixture(autouse=True)
def _clean_cache():
    spend.reset_cache()
    yield
    spend.reset_cache()


# --------------------------------------------------------------------------- DB-less


def test_disabled_when_cap_unset(monkeypatch):
    monkeypatch.setattr(settings, "platform_spend_cap_usd", 0.0)
    assert spend.over_spend_cap() is False


def test_fails_open_when_db_down(monkeypatch):
    monkeypatch.setattr(settings, "platform_spend_cap_usd", 1.0)

    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(spend, "SessionLocal", _boom)
    # Cap enabled but the query can't run → serve anyway (availability over enforcement).
    assert spend.over_spend_cap() is False


def test_runs_refused_with_sse_error_when_capped(monkeypatch):
    monkeypatch.setattr(spend, "over_spend_cap", lambda: True)
    graph = input_agent_output(model="fake").model_dump()
    r = client.post("/runs", json={"graph": graph, "message": "hi"})
    assert r.status_code == 200
    body = r.text
    assert '"type": "error"' in body
    assert "[DONE]" in body
    assert '"type": "token"' not in body  # refused before running — no tokens


def test_assist_refused_with_sse_error_when_capped(monkeypatch):
    monkeypatch.setattr(spend, "over_spend_cap", lambda: True)
    r = client.post("/assist", json={"messages": [{"role": "user", "content": "hi"}]})
    assert r.status_code == 200
    body = r.text
    assert '"type": "error"' in body
    assert "[DONE]" in body
    assert '"type": "graph"' not in body  # refused before drafting


# --------------------------------------------------------------------------- DB-backed


@pytest.mark.skipif(not _db_available(), reason="Postgres not available")
def test_cap_trips_at_the_boundary(monkeypatch):
    from calypr_api.db.models import Run

    # Seed a known cost so month-to-date spend is comfortably above zero.
    with SessionLocal() as s:
        set_tenant(s, DEV_WORKSPACE_ID)
        s.add(
            Run(
                workspace_id=uuid.UUID(DEV_WORKSPACE_ID),
                source="api",
                status="completed",
                cost_usd=Decimal("5.00"),
            )
        )
        s.commit()

    base = spend._month_to_date_spend()
    assert base >= 5.0

    # spend >= cap ⇒ over (boundary is inclusive)
    monkeypatch.setattr(settings, "platform_spend_cap_usd", base)
    spend.reset_cache()
    assert spend.over_spend_cap() is True

    # spend just under cap ⇒ not over
    monkeypatch.setattr(settings, "platform_spend_cap_usd", base + 0.01)
    spend.reset_cache()
    assert spend.over_spend_cap() is False
