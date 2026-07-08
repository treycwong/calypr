"""App lifespan: swap in the durable Postgres checkpointer, but fall back to in-memory on any
failure so keyless CI / DB-less dev still boot (WEEK2 plan §C2)."""

from __future__ import annotations

import pytest
from calypr_api import engine, main
from calypr_api.db.session import engine as db_engine
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import text


def _db_available() -> bool:
    try:
        with db_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def _restore_checkpointer():
    """Leave the process-wide checkpointer as a fresh in-memory saver so other test modules
    (which reuse `app` without entering the lifespan) aren't handed a closed connection."""
    original = engine.checkpointer
    yield
    engine.checkpointer = original if isinstance(original, InMemorySaver) else InMemorySaver()


async def test_falls_back_to_memory_when_checkpointer_fails(monkeypatch):
    def _boom(_url):
        raise RuntimeError("no postgres")

    monkeypatch.setattr(main, "postgres_checkpointer", _boom)
    engine.checkpointer = InMemorySaver()
    async with main.lifespan(main.app):
        assert isinstance(engine.checkpointer, InMemorySaver)  # unchanged — fell back


@pytest.mark.skipif(not _db_available(), reason="Postgres not available")
async def test_enables_durable_checkpointer_when_db_up():
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    engine.checkpointer = InMemorySaver()
    async with main.lifespan(main.app):
        assert isinstance(engine.checkpointer, AsyncPostgresSaver)
