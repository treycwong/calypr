"""Shared test setup: keep the suite independent of the developer's `.env`.

`config.py` calls `load_dotenv` on the repo-root `.env`, so anything a developer sets there is
also set while the tests run. That is fine for most settings and actively wrong for one.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

import pytest
from calypr_api.config import settings
from calypr_api.db.models import Account, Workspace
from calypr_api.db.session import SessionLocal, engine
from sqlalchemy import text


@dataclass(frozen=True)
class Tenant:
    """An account and one of its workspaces.

    Since 0016 the two are different things — the account pays (plan, credits, Stripe) and the
    workspace holds the work — so a test that wants "a Plus tenant" needs both. Handing back
    both ids keeps tests from having to re-derive one from the other and from accidentally
    depending on the migration-era coincidence that they were once equal."""

    account_id: uuid.UUID
    workspace_id: uuid.UUID


@pytest.fixture
def tenant_factory():
    """Throwaway account + workspace pairs, removed afterwards (everything cascades)."""
    made: list[uuid.UUID] = []

    def make(plan: str = "free", *, workspaces: int = 1, name: str | None = None) -> Tenant:
        label = name or f"test-{uuid.uuid4().hex[:8]}"
        with SessionLocal() as s:
            account = Account(plan=plan)
            s.add(account)
            s.flush()
            first: Workspace | None = None
            for i in range(workspaces):
                ws = Workspace(
                    account_id=account.id, name=label if i == 0 else f"{label}-{i}"
                )
                s.add(ws)
                s.flush()
                first = first or ws
            s.commit()
            made.append(account.id)
            assert first is not None
            return Tenant(account_id=account.id, workspace_id=first.id)

    yield make

    with SessionLocal() as s:
        s.query(Account).filter(Account.id.in_(made)).delete(synchronize_session=False)
        s.commit()


@pytest.fixture(scope="session", autouse=True)
def _checkpoint_tables():
    """Make sure LangGraph's checkpoint tables exist before any test writes to them.

    They are created by `AsyncPostgresSaver.setup()`, not Alembic, so until now they appeared
    only as a **side effect of whichever test module first entered the app lifespan** — in
    practice `test_lifespan.py`. Every other module that touches `checkpoints` was silently
    relying on running after it.

    Alphabetical collection order is what makes that a trap rather than a nuisance: a new module
    sorting before `test_lifespan` finds no tables and fails, while the same code passes locally
    against a developer database where the app has run at least once. `test_downgrade.py` hit
    exactly that, and it was green locally and red in CI.

    Session-scoped and idempotent — `setup()` is safe to re-run, and a database that isn't
    reachable is left to the per-module `requires_db` skips."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return  # no database; `requires_db` handles the skipping

    async def _setup() -> None:
        from calypr_runtime.checkpoint import postgres_checkpointer

        async with postgres_checkpointer(settings.database_url) as cp:
            await cp.setup()

    try:
        asyncio.run(_setup())
    except Exception:  # pragma: no cover - a checkpointer we can't build is the module's problem
        pass


@pytest.fixture(autouse=True)
def _unmetered_by_default(monkeypatch):
    """Force `internal_key` empty unless a test opts in.

    `CALYPR_INTERNAL_KEY` is the switch that turns on tenant scoping and the billing gates
    (`credits.check_can_run`, `run_access.check_run_gates`, `deps.require_code_export`). The
    suite is written for it being unset — the same carve-out that keeps CI and `start.sh`
    working without keys or a database.

    Setting it locally to exercise the paid tiers therefore broke 33 tests that had nothing to
    do with billing: requests started 401ing for want of a proxy header no test sends. The suite
    should not depend on whether a developer happens to be testing enforcement that day, so the
    default is pinned here and the tests that *want* enforcement set it themselves with
    `monkeypatch.setattr(settings, "internal_key", "prod-key")` — an explicit opt-in that reads
    as part of the test rather than as ambient state.
    """
    monkeypatch.setattr(settings, "internal_key", "")
