"""Calypr API entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from calypr_runtime.checkpoint import postgres_checkpointer
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from calypr_api import engine as engine_mod
from calypr_api.config import settings
from calypr_api.db.session import engine
from calypr_api.middleware import PostHogMiddleware
from calypr_api.routers import (
    agents,
    assist,
    connectors,
    provider_keys,
    runs,
    share,
    uploads,
    waitlist,
)

log = logging.getLogger("calypr_api")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Swap in the durable Postgres checkpointer for the app's lifetime, so playground threads
    survive restarts. Any failure (keyless CI, DB-less dev, pooler issue) keeps the in-memory
    saver — the app still serves, threads just don't persist (WEEK2 plan §C2)."""
    stack = AsyncExitStack()
    try:
        url = settings.checkpoint_database_url or settings.database_url
        cp = await stack.enter_async_context(postgres_checkpointer(url))
        await cp.setup()  # idempotent — creates checkpoint tables on first boot
        engine_mod.checkpointer = cp
        log.info("durable Postgres checkpointer enabled")
    except Exception:
        log.warning("durable checkpointer unavailable — using in-memory", exc_info=True)
    try:
        yield
    finally:
        await stack.aclose()


def create_app() -> FastAPI:
    app = FastAPI(title="Calypr API", version="0.0.0", lifespan=lifespan)

    app.add_middleware(PostHogMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(OperationalError)
    async def _db_unavailable(_request: Request, _exc: OperationalError) -> JSONResponse:
        """Postgres unreachable → a quiet 503, not a wall-of-text 500 traceback. Lets DB-less
        local dev (start.sh without Docker) stay usable: data routes return 503, which the web
        app already tolerates, while compile/codegen/run/assist keep working without a DB."""
        log.warning("database unavailable — returning 503")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "database unavailable"},
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness: the process is up."""
        return {"status": "ok", "service": "calypr-api"}

    @app.get("/readyz", tags=["meta"])
    def readyz(response: Response) -> dict[str, str]:
        """Readiness: returns 503 if the database is unreachable. Also reports which
        checkpointer the lifespan installed — `postgres` (durable) vs `memory` (fallback) —
        so durable-vs-fallback is queryable in prod instead of buried in an INFO log."""
        checkpointer = (
            "memory"
            if isinstance(engine_mod.checkpointer, InMemorySaver)
            else "postgres"
        )
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "degraded", "db": "unreachable", "checkpointer": checkpointer}
        return {
            "status": "ready",
            "environment": settings.environment,
            "db": "ok",
            "checkpointer": checkpointer,
        }

    app.include_router(agents.router)
    app.include_router(runs.router)
    app.include_router(assist.router)
    app.include_router(share.router)
    app.include_router(uploads.router)
    app.include_router(connectors.router)
    app.include_router(provider_keys.router)
    app.include_router(waitlist.router)
    return app


app = create_app()
