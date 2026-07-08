"""Checkpointer helpers. In-memory for tests/dev; Postgres for durable runs (HITL,
resumable threads) per CLAUDE-PLAN.md §8."""

from __future__ import annotations

from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import InMemorySaver


def memory_checkpointer() -> InMemorySaver:
    return InMemorySaver()


def _normalize_conn(database_url: str) -> str:
    # AsyncPostgresSaver wants a plain postgresql:// DSN, not the SQLAlchemy driver form.
    return database_url.replace("postgresql+psycopg://", "postgresql://")


@asynccontextmanager
async def postgres_checkpointer(database_url: str, *, min_size: int = 1, max_size: int = 4):
    """Async context manager yielding an AsyncPostgresSaver backed by a connection **pool**.

    A pool (not `from_conn_string`'s single long-lived connection) is required for a
    long-running server: that one connection goes stale on the provider's idle timeout and then
    every run fails with "the connection is closed". The pool health-checks each connection on
    checkout (`check_connection`) and transparently reconnects a dead one.

    Usage:
        async with postgres_checkpointer(url) as cp:
            await cp.setup()  # idempotent — creates checkpoint tables on first use
            ...
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    pool = AsyncConnectionPool(
        conninfo=_normalize_conn(database_url),
        min_size=min_size,
        max_size=max_size,
        open=False,
        check=AsyncConnectionPool.check_connection,  # ping + reconnect stale conns on checkout
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
            # No server-side prepared statements — keeps the pool safe through a transaction
            # pooler and matches what the checkpointer needs.
            "prepare_threshold": None,
        },
    )
    await pool.open(wait=True, timeout=10)
    try:
        yield AsyncPostgresSaver(conn=pool)
    finally:
        await pool.close()
