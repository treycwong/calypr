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
| `CALYPR_NOTION_*` | **Yes — Notion is live** | `CALYPR_NOTION_MCP_URL`, `CALYPR_NOTION_MCP_AUTH`, `CALYPR_NOTION_CLIENT_ID/SECRET`, `CALYPR_OAUTH_REDIRECT_BASE`. Leaving them unset makes `Connect Notion` return 501 — a safe fallback, not the intended state. |

### Vercel (web) — existing

`CALYPR_API_URL` (Railway API URL), `CALYPR_INTERNAL_KEY` (same as API), `BETTER_AUTH_SECRET`,
`DATABASE_URL`, GitHub OAuth creds — unchanged by this branch.

## What's live

All of it, as of **2026-07-22**:

- **Connectors (Tier B)** — any HTTPS MCP server + optional bearer, encrypted.
- **BYO provider API keys** — OpenAI/Anthropic/Tavily.
- **Notion Tier A** — `notion-mcp` runs as its own Railway service (`infra/notion-mcp/`), the
  OAuth flow is state-hardened, and the `CALYPR_NOTION_*` vars are set. **Verified working in
  production by the founder** (Notion + Tavily on one agent), which is the bar this file cares
  about — the section below is kept as the setup runbook for rebuilding it.
- **Tavily search** — executes for real on the canvas, keyed per workspace or from the server env.

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

## Notion Tier A — setup runbook (done; keep for rebuilds)

1. Deploy `@notionhq/notion-mcp-server` as a separate Railway service in the same project,
   using **`infra/notion-mcp/`** (Dockerfile + `railway.json`). Set `AUTH_TOKEN` on that service
   to a long random secret; the image reads the bearer from the environment. The "internal port
   == published port" rule is a *local-only* constraint — with bearer auth the server does no
   `Host` validation, so Railway's domain and `$PORT` work as-is. Full walkthrough in
   `infra/CONNECTORS.md` → "Production (Railway)".
2. Set `CALYPR_NOTION_MCP_URL`, `CALYPR_NOTION_MCP_AUTH`, `CALYPR_NOTION_CLIENT_ID/SECRET`,
   `CALYPR_OAUTH_REDIRECT_BASE=https://calypr.co`, and register the redirect URI
   `https://calypr.co/api/connectors/notion/callback` in the Notion integration.
3. ~~**Add an OAuth `state` parameter** to the connect/callback flow (CSRF hardening).~~ **Done.**
   `connect` mints a signed, workspace-bound, 10-minute state (`calypr_api/oauth_state.py`) and
   `callback` refuses anything else *before* the code is exchanged. Signed with
   `CALYPR_VAULT_KEY` when set, else the Notion client secret — so no new env var, but set the
   vault key in prod anyway (it is already required). Steps 1–2 remain.

See `infra/CONNECTORS.md` for the full connector setup.
