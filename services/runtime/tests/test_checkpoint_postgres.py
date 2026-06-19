"""Durable-checkpointer smoke test against the running Postgres. Skipped when the
database isn't reachable (so DB-less runs stay green)."""

from __future__ import annotations

import os
import socket

import pytest
from calypr_compiler.golden import input_agent_output
from calypr_model import FakeModelClient
from calypr_nodes import NodeContext
from calypr_runtime import run
from calypr_runtime.checkpoint import postgres_checkpointer

DB_URL = os.environ.get(
    "CALYPR_DATABASE_URL", "postgresql+psycopg://calypr:calypr@localhost:5432/calypr"
)


def _pg_available() -> bool:
    try:
        socket.create_connection(("localhost", 5432), timeout=0.5).close()
        return True
    except OSError:
        return False


pytestmark = pytest.mark.skipif(not _pg_available(), reason="Postgres not available")


async def test_run_with_postgres_checkpointer():
    spec = input_agent_output(model="fake")
    ctx = NodeContext(model=FakeModelClient(reply="durable hi"))
    async with postgres_checkpointer(DB_URL) as cp:
        await cp.setup()  # creates checkpoint tables on first use
        state = await run(
            spec, ctx, "hello", thread_id="pg-phase1", checkpointer=cp
        )
    assert state["output"] == "durable hi"
