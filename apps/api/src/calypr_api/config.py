"""Application settings, loaded from env (prefix CALYPR_) with sane local defaults."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load the repo-root .env into the process environment so provider SDKs
# (OPENAI_API_KEY, ANTHROPIC_API_KEY, …) pick up local keys. No-op in production,
# where these are set directly. Path is relative to this file, not the cwd.
load_dotenv(Path(__file__).resolve().parents[4] / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CALYPR_", env_file=".env", extra="ignore"
    )

    environment: str = "development"
    # Web origin(s) allowed to call the API directly (CORS). The web app normally
    # proxies server-side, so this is a dev convenience.
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3100"]
    # Postgres + pgvector. Wired to docker-compose in the DB task.
    database_url: str = "postgresql+psycopg://calypr:calypr@localhost:5432/calypr"
    # Auth seam: "dev" (local cookie) or "clerk" (JWT). See CLAUDE-PLAN.md Phase 0.
    auth_provider: str = "dev"
    # Shared secret the Next proxy presents (X-Calypr-Internal-Key) to prove it's the trusted
    # caller; when set, requests are scoped to the X-Calypr-User-Id's workspace. Unset (local/CI)
    # → every request falls back to the shared dev workspace.
    internal_key: str = ""
    # Default model the AI assistant drafts graphs with. Unset → the keyless `fake` path, so
    # dev/CI stay key-free (AI-ASSISTANT-SPEC.md §4). Set e.g. "kimi-k2" / "deepseek-chat" /
    # "gpt-4.1-mini" in prod (provider base URLs + keys come from the model factory's env).
    assistant_model: str = ""
    # Interim abuse guardrail before usage-based billing exists: max assist calls per
    # workspace per day, enforced in the router (AI-ASSISTANT-SPEC.md §8).
    assist_daily_cap: int = 50


settings = Settings()
