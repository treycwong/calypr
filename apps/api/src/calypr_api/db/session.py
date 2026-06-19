"""Engine + session factory, plus the per-request tenant scoping helper for RLS."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from calypr_api.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(
    bind=engine, autoflush=False, expire_on_commit=False, class_=Session
)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a DB session."""
    with SessionLocal() as session:
        yield session


def set_tenant(session: Session, workspace_id: str) -> None:
    """Scope a session to a tenant for the duration of the transaction.

    Sets the `calypr.workspace_id` GUC that RLS policies read (CLAUDE-PLAN.md §6).
    Every tenant-scoped query must run after this is set.
    """
    session.execute(
        text("SELECT set_config('calypr.workspace_id', :wid, false)"),
        {"wid": str(workspace_id)},
    )
