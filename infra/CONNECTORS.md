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
| `CALYPR_NOTION_MCP_URL` | The self-hosted `@notionhq/notion-mcp-server` endpoint, e.g. `http://localhost:3100/mcp`. | Unset ⇒ Notion connectors save but won't resolve at run time. |
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
   `infra/docker/compose.yaml` as the `notion-mcp` service on `localhost:3100`):
   ```
   npx -y @notionhq/notion-mcp-server --transport http --host 0.0.0.0 \
     --port 3100 --enable-token-passthrough --unsafe-disable-auth
   ```
   Set `CALYPR_NOTION_MCP_URL=http://localhost:3100/mcp`.

   Two gotchas the compose file already handles:
   - **The internal port must equal the published port.** The server's DNS-rebinding
     protection validates the `Host` header against its own host:port, so a `3100→3000`
     remap is rejected with `Invalid Host header`. Run it on `--port 3100` and publish
     `3100:3100`.
   - **The server requires its own bearer** unless started with `--unsafe-disable-auth`.
     For production, drop that flag, pass `--auth-token <secret>`, and set
     `CALYPR_NOTION_MCP_AUTH` to the same value (Calypr then sends the bearer too).
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
