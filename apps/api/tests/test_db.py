"""Integration tests for the DB scaffolding. Skipped when Postgres is unavailable
(so DB-less unit runs stay green). Requires `alembic upgrade head` to have run."""

from __future__ import annotations

import uuid

import pytest
from calypr_api.db.session import SessionLocal, engine, set_tenant
from sqlalchemy import text


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="Postgres not available")


def test_pgvector_extension_installed():
    with engine.connect() as conn:
        ext = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).scalar()
        assert ext == 1


def test_workspace_table_and_rls():
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('public.workspace')")).scalar() == "workspace"
        rls_on = conn.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = 'workspace'")
        ).scalar()
        assert rls_on is True
        policies = conn.execute(
            text("SELECT count(*) FROM pg_policies WHERE tablename = 'workspace'")
        ).scalar()
        assert policies >= 1


def test_set_tenant_sets_guc():
    with SessionLocal() as session:
        wid = str(uuid.uuid4())
        set_tenant(session, wid)
        got = session.execute(text("SELECT current_setting('calypr.workspace_id', true)")).scalar()
        assert got == wid
