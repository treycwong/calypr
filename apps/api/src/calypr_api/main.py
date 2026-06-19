"""Calypr API entrypoint.

Phase 0: health/readiness only. Routers (agents, runs, knowledge) land in later phases.
"""

from __future__ import annotations

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from calypr_api.config import settings
from calypr_api.db.session import engine


def create_app() -> FastAPI:
    app = FastAPI(title="Calypr API", version="0.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness: the process is up."""
        return {"status": "ok", "service": "calypr-api"}

    @app.get("/readyz", tags=["meta"])
    def readyz(response: Response) -> dict[str, str]:
        """Readiness: returns 503 if the database is unreachable."""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "degraded", "db": "unreachable"}
        return {"status": "ready", "environment": settings.environment, "db": "ok"}

    return app


app = create_app()
