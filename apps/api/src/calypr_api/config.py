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
    # Connection for the LangGraph durable checkpointer. Falls back to `database_url` when
    # unset. MUST be a *direct* (non-pooler) endpoint: the checkpointer opens its own psycopg
    # connection with prepared statements enabled, which a transaction pooler (Neon `-pooler`,
    # pgBouncer) can't hold across checkouts (WEEK2 plan §C3).
    checkpoint_database_url: str = ""
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
    # PostHog analytics. Token is empty in dev/CI (no-ops silently when unset).
    posthog_project_token: str = ""
    posthog_host: str = "https://us.i.posthog.com"
    # Platform-wide loss firewall (PRICING-SPEC §9): if the sum of this month's `run.cost_usd`
    # reaches this many USD, new runs/assists are refused with an SSE error. 0/unset ⇒ disabled.
    platform_spend_cap_usd: float = 0.0

    # Connector credential vault (MCP-NODE-PLAN §5). Master secret for Fernet envelope
    # encryption; any string works. Unset → an insecure dev key in non-prod, fail-closed in prod.
    vault_key: str = ""
    # Public base URL the browser is redirected back to after an OAuth consent (no trailing
    # slash), e.g. "https://calypr.co". The connector callback path is appended. Unset → the
    # request's own origin is used (fine for local dev).
    oauth_redirect_base: str = ""
    # Notion connector (Tier A, Path A — classic public-integration OAuth). Client id/secret of
    # a Notion public integration; unset ⇒ the "Connect Notion" flow is disabled (501).
    notion_client_id: str = ""
    notion_client_secret: str = ""
    # The self-hosted `@notionhq/notion-mcp-server` (run with --enable-token-passthrough) that
    # Calypr connects to, passing each workspace's Notion bot token via the `Notion-Token`
    # header. Unset ⇒ Notion connectors can be created but won't resolve at run time.
    notion_mcp_url: str = ""
    # The Notion MCP server's own bearer token (its `--auth-token`). Sent as `Authorization:
    # Bearer` alongside the per-request `Notion-Token`. Leave unset only when the server runs
    # with `--unsafe-disable-auth` (isolated localhost dev).
    notion_mcp_auth: str = ""


settings = Settings()
