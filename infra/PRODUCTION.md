# Production deployment — connectors, vault, BYO keys

This branch adds a credential vault, MCP connectors (Tier B), BYO provider keys, and Notion
(Tier A, **deferred** in the first cut). It is designed to deploy with no behavior change to
existing runs: every new code path falls back to the server env / degrades to zero tools when
unconfigured.

## Topology (unchanged)

- **API** — Railway (Docker, `apps/api/Dockerfile`). Migrations run automatically on deploy via
  `railway.json` `preDeployCommand: alembic … upgrade head`, so **`0006_connectors` and
  `0007_provider_keys` apply themselves** — no manual migration step.
- **Web** — Vercel (calypr.co).
- **Postgres** — Neon.

## Required environment variables

### Railway (API)

| Var | Required? | Notes |
|---|---|---|
| `CALYPR_ENVIRONMENT` | **Yes** | Set to `production`. |
| `CALYPR_VAULT_KEY` | **Yes** | Master secret for the credential vault (any strong string). Fail-closed: the vault refuses to encrypt/decrypt if this is unset **and** the deployment looks production-like (`CALYPR_ENVIRONMENT=production` *or* `CALYPR_INTERNAL_KEY` set). Set a long random value and **never rotate it** without re-encrypting existing rows. |
| `CALYPR_INTERNAL_KEY` | Yes (existing) | Shared secret the Vercel proxy presents; also a production signal for the vault fail-closed. Must match the web value. |
| `CALYPR_DATABASE_URL` / `CALYPR_CHECKPOINT_DATABASE_URL` | Yes (existing) | Neon. Checkpoint URL must be a direct (non-pooler) endpoint. |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `TAVILY_API_KEY` | As used | Server defaults. A workspace's BYO key (Settings → API Keys) overrides these per run; unset just means BYO-only for that provider. |
| `CALYPR_NOTION_*` | **Leave unset** | Notion Tier A is deferred (see below). |

### Vercel (web) — existing

`CALYPR_API_URL` (Railway API URL), `CALYPR_INTERNAL_KEY` (same as API), `BETTER_AUTH_SECRET`,
`DATABASE_URL`, GitHub OAuth creds — unchanged by this branch.

## What ships now vs. deferred

- **Ships:** Connectors (Tier B — any HTTPS MCP server + optional bearer, encrypted), BYO
  provider API keys (OpenAI/Anthropic/Tavily). All env-driven, no extra infra.
- **Deferred: Notion Tier A.** Requires a long-running `notion-mcp` server Vercel can't host.
  With `CALYPR_NOTION_CLIENT_ID` unset, **Connect Notion returns 501** and no Notion code path is
  reachable. Connectors already degrade gracefully when `CALYPR_NOTION_MCP_URL` is unset.

## Security posture (verified this branch)

- **Tenant isolation:** RLS policies on `connector_credential` + `provider_key` (migrations
  0006/0007) *and* explicit `workspace_id` filters in every query (defense in depth — matches the
  existing `agent`/`run` tables). Note: no table uses `FORCE ROW LEVEL SECURITY`, so RLS is only
  enforced if the app's DB role is **not** the table owner; the app-level filters hold regardless.
- **Secrets at rest:** Fernet envelope encryption; secrets are write-only (never returned or
  logged — only ids/provider names/URLs are logged); codegen reads keys from `os.environ`.
- **SSRF guard:** Tier B connector URLs resolving to loopback/private/link-local/metadata
  addresses are rejected on real deployments (at save + at use time). Off in local dev/CI so
  tests can reach localhost servers.
- **Vault fail-closed:** refuses the insecure dev fallback key whenever a production signal is
  present.

## Before enabling Notion Tier A (later)

1. Deploy `@notionhq/notion-mcp-server` as a separate service (Railway) with **`--auth-token
   <secret>`** (not the local `--unsafe-disable-auth`), internal port == published port.
2. Set `CALYPR_NOTION_MCP_URL`, `CALYPR_NOTION_MCP_AUTH`, `CALYPR_NOTION_CLIENT_ID/SECRET`,
   `CALYPR_OAUTH_REDIRECT_BASE=https://calypr.co`, and register the redirect URI
   `https://calypr.co/api/connectors/notion/callback` in the Notion integration.
3. **Add an OAuth `state` parameter** to the connect/callback flow (CSRF hardening) — tracked as
   a required pre-Notion fix (see the security review).

See `infra/CONNECTORS.md` for the full connector setup.
