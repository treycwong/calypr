"""Application settings, loaded from env (prefix CALYPR_) with sane local defaults."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CALYPR_", env_file=".env", extra="ignore"
    )

    environment: str = "development"
    # Web origin(s) allowed to call the API (CORS).
    cors_origins: list[str] = ["http://localhost:3000"]
    # Postgres + pgvector. Wired to docker-compose in the DB task.
    database_url: str = "postgresql+psycopg://calypr:calypr@localhost:5432/calypr"
    # Auth seam: "dev" (local cookie) or "clerk" (JWT). See CLAUDE-PLAN.md Phase 0.
    auth_provider: str = "dev"


settings = Settings()
