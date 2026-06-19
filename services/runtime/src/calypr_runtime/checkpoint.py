"""Checkpointer helpers. In-memory for tests/dev; Postgres for durable runs (HITL,
resumable threads) per CLAUDE-PLAN.md §8."""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver


def memory_checkpointer() -> InMemorySaver:
    return InMemorySaver()


def _normalize_conn(database_url: str) -> str:
    # AsyncPostgresSaver wants a plain postgresql:// DSN, not the SQLAlchemy driver form.
    return database_url.replace("postgresql+psycopg://", "postgresql://")


def postgres_checkpointer(database_url: str):
    """Return an async context manager yielding an AsyncPostgresSaver.

    Usage:
        async with postgres_checkpointer(url) as cp:
            await cp.setup()  # first run only — creates checkpoint tables
            ...
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    return AsyncPostgresSaver.from_conn_string(_normalize_conn(database_url))
