# The self-hosted Notion MCP server, packaged for Railway (Tier A connector).
#
# One instance serves every workspace: `--enable-token-passthrough` makes it read each request's
# Notion bot token from the `Notion-Token` header, which Calypr resolves from the vault at run
# time (see apps/api/src/calypr_api/connectors.py). Its *own* bearer (AUTH_TOKEN) gates /mcp and
# must match CALYPR_NOTION_MCP_AUTH on the API service.
#
# Pinned rather than floating: this process holds every workspace's Notion access, so an
# unreviewed upstream release should never roll out by itself. Bump deliberately.
FROM node:22-alpine

ENV NODE_ENV=production
RUN npm install -g @notionhq/notion-mcp-server@2.4.1

# Railway assigns $PORT at run time and the server has no PORT env fallback (it only reads
# --port), so the shell form is required to expand it. 3000 is just the local default.
#
# --host 0.0.0.0 serves Railway's public domain. For private networking (IPv6-only) use `::`.
#
# No --unsafe-disable-auth here: that flag is what turns the server's DNS-rebinding protection
# on, which in turn pins the allowed Host header to its own host:port and rejects a public
# domain. With bearer auth (the AUTH_TOKEN env var) that protection is off, so Railway's
# hostname works as-is — which is why the local compose file's "internal port must equal
# published port" gotcha does not apply to this image.
EXPOSE 3000
CMD ["sh", "-c", "notion-mcp-server --transport http --host 0.0.0.0 --port ${PORT:-3000} --enable-token-passthrough"]
