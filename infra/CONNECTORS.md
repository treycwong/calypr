# Connectors — credential vault, MCP servers, and Notion (Tier A)

Connectors let a workspace attach external tools to an MCP Tool node without ever putting a
secret in the canvas DSL. Secrets are Fernet-encrypted in the `connector_credential` table
(`apps/api/src/calypr_api/vault.py`); the canvas stores only a `mcp_connector_ref`, and the run
path resolves it to a live URL + headers server-side just before compile
(`apps/api/src/calypr_api/connectors.py`).

## Environment variables

| Var | Purpose | Notes |
|---|---|---|
| `CALYPR_VAULT_KEY` | Master secret for envelope encryption (any string). | **Required in production** — fail-closed if unset. In dev/CI an insecure fixed key is used so tests stay key-free. |
| `CALYPR_OAUTH_REDIRECT_BASE` | Public web origin OAuth returns to, e.g. `https://calypr.co`. | The callback path `/api/connectors/notion/callback` is appended. Required for Notion. |
| `CALYPR_NOTION_CLIENT_ID` / `CALYPR_NOTION_CLIENT_SECRET` | A Notion **public** integration's OAuth credentials. | Unset ⇒ the "Connect Notion" flow returns 501. |
| `CALYPR_NOTION_MCP_URL` | The self-hosted `@notionhq/notion-mcp-server` endpoint, e.g. `http://localhost:3333/mcp`. | Unset ⇒ Notion connectors save but won't resolve at run time. |
| `CALYPR_NOTION_MCP_AUTH` | The Notion MCP server's own bearer (`--auth-token`), sent as `Authorization: Bearer` alongside `Notion-Token`. | Leave unset only when the server runs with `--unsafe-disable-auth` (isolated localhost). |

## Tier B — any HTTP MCP server (no OAuth)

Settings → **MCP servers** → paste a name + `https://…/mcp` URL + optional bearer → **Add
server**. The bearer is encrypted at rest. On a Tool node, pick the connector from the
**Connector** dropdown. **Test** runs a live `ListTools` probe.

## Tier A — Notion (Path A: classic OAuth → self-hosted MCP server)

The hosted `mcp.notion.com` server uses its own browser OAuth and rejects integration tokens,
so Calypr uses a **public Notion integration** + a **self-hosted** Notion MCP server:

1. **Create a Notion public integration** at <https://www.notion.so/my-integrations> (type:
   Public). Set the OAuth redirect URI to `${CALYPR_OAUTH_REDIRECT_BASE}/api/connectors/notion/callback`.
   Copy the client ID/secret into `CALYPR_NOTION_CLIENT_ID` / `CALYPR_NOTION_CLIENT_SECRET`.
2. **Run the Notion MCP server** with token passthrough (already wired in
   `infra/docker/compose.yaml` as the `notion-mcp` service on `localhost:3333`):
   ```
   npx -y @notionhq/notion-mcp-server --transport http --host 0.0.0.0 \
     --port 3333 --enable-token-passthrough --unsafe-disable-auth
   ```
   Set `CALYPR_NOTION_MCP_URL=http://localhost:3333/mcp`.

   Two gotchas the compose file already handles:
   - **The internal port must equal the published port.** The server's DNS-rebinding
     protection validates the `Host` header against its own host:port, so a remap (e.g.
     `3333→3000`) is rejected with `Invalid Host header`. Run it on `--port 3333` and publish
     `3333:3333`. 3333 is deliberately outside the web range (dev web 3000, e2e web 3100).
     **This applies to the local setup only** — see the note under Production below.
   - **The server requires its own bearer** unless started with `--unsafe-disable-auth`.
     For production, drop that flag, pass a bearer, and set `CALYPR_NOTION_MCP_AUTH` to the
     same value (Calypr then sends the bearer too).

   ### Production (Railway)

   `infra/notion-mcp/` holds a Dockerfile + `railway.json` for this. Deploy it as a **second
   Railway service in the same project** as the API:

   1. New service → same GitHub repo → set its config path to `infra/notion-mcp/railway.json`
      (or point the service's Dockerfile path at `infra/notion-mcp/Dockerfile`).
   2. On that service set **`AUTH_TOKEN`** to a long random secret. The image reads it from the
      environment rather than the command line, so the bearer never sits in a start command or
      a build log. Generate one with `openssl rand -hex 32`.
   3. Give it a public domain (or use private networking — see below) and note the URL.
   4. On the **API** service set `CALYPR_NOTION_MCP_URL=https://<that-domain>/mcp` and
      `CALYPR_NOTION_MCP_AUTH=<the same AUTH_TOKEN>`.

   Three things worth knowing, all verified against `@notionhq/notion-mcp-server@2.4.1`:

   - **The Host-header gotcha above does not apply in production.** The server only enables
     DNS-rebinding protection when `--unsafe-disable-auth` is passed; with bearer auth it does
     no `Host` validation, so Railway's own domain is accepted and `$PORT` can be anything.
     (Confirmed: a request carrying `Host: notion-mcp.up.railway.app` reaches the app.)
   - **`$PORT` must be expanded in the command.** The server reads `--port` only — there is no
     `PORT` environment fallback — which is why the image's `CMD` uses the shell form.
   - **`/health` is registered before the bearer middleware**, so Railway's healthcheck passes
     without credentials. Only `/mcp` is gated.

   Private networking is the tighter option (the MCP server is then unreachable from the
   internet): use `http://<service-name>.railway.internal:<port>/mcp` for
   `CALYPR_NOTION_MCP_URL`. Railway's private network is IPv6-only, so the container must bind
   `--host ::` instead of `0.0.0.0` — change the `CMD` if you go this route. Keep `AUTH_TOKEN`
   set either way; it is what stops any other service in the project from reading Notion data.
3. **Connect** in Settings → **Connected accounts → Connect Notion**. The browser completes the
   Notion consent flow; the callback exchanges the code for a bot token, which is encrypted and
   stored. At run time Calypr connects to the Notion MCP server, passing that token via the
   `Notion-Token` header — one server instance serves every workspace.

## Security posture

- The canvas/DSL never carries a secret — only a `mcp_connector_ref` (a vault handle).
- Tokens are Fernet-encrypted at rest and RLS-scoped to the workspace (migration `0006`).
- `/connectors` responses never echo a secret — only a `has_secret` flag.
- A connector that fails to resolve (revoked/absent) degrades to zero tools (the agent answers)
  rather than crashing the run.
