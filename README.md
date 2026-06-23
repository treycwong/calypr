# Calypr

A multi-tenant SaaS for designing AI agents on a visual canvas that compiles to
**LangGraph** and runs in a hosted runtime.

- **Architecture & roadmap:** [`CLAUDE-PLAN.md`](./CLAUDE-PLAN.md) (foundational building blocks + phased plan)
- **Foundation plan:** [`PLAN.md`](./PLAN.md) · **Growth plan:** [`MVP.md`](./MVP.md)

## Monorepo layout

```
apps/
  web/        # Next.js + React Flow canvas, dashboard, playground   (@calypr/web)
  api/        # FastAPI: auth, agents CRUD, compile, run, knowledge   (calypr-api)
packages/
  dsl/        # GraphSpec (Pydantic) → generated TS — the contract     (calypr-dsl / @calypr/dsl)
  nodes/      # node registry + node types  (Phase 1)
  ui/         # shared React components      (Phase 2)
services/     # compiler, runtime, model, ingestion, tools  (Phase 1+)
e2e/          # Playwright end-to-end gate tests             (@calypr/e2e)
infra/        # docker-compose, alembic
```

## Stack

Next.js · React Flow (xyflow) · FastAPI · LangGraph · Postgres + pgvector · uv (Python) · pnpm (JS).

## Develop

Prerequisites: Node ≥ 20 (with Corepack), Python 3.12 via [uv](https://docs.astral.sh/uv/), Docker.

```bash
corepack enable                # activate pnpm
pnpm install                   # JS workspaces
uv sync                        # Python workspace venv
docker compose -f infra/docker/compose.yaml up -d   # Postgres + pgvector

./start.sh                     # ⭐ start BOTH servers (api :8000 + web :3100); Ctrl-C stops both

# …or run them manually in two terminals:
uv run uvicorn calypr_api.main:app --reload --port 8000          # api → http://localhost:8000
pnpm --filter @calypr/web exec next dev --port 3100              # web → http://localhost:3100
```

`start.sh` auto-loads `.env` (so OpenAI/Anthropic keys are picked up), brings up Postgres if
Docker is running (only needed to *save* agents — chat + the Code view work without it), and
streams both servers' logs. Override ports with `API_PORT` / `WEB_PORT`.

### Auth

The web app ships a **keyless dev sign-in** so it runs locally and in CI with no setup. To
switch the whole app to **[Clerk](https://clerk.com)**, set two env vars (in `apps/web/.env.local`)
— no code changes:

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
```

When present, the layout wraps in `ClerkProvider`, the proxy gates with Clerk, and the
sign-in page + account menu render Clerk's UI. When absent, the dev cookie sign-in is used.
The single seam is `getSession()` in [`apps/web/src/lib/auth.ts`](apps/web/src/lib/auth.ts).

### Tests

```bash
uv run pytest                  # backend (api + dsl)
pnpm --filter @calypr/dsl gen:check   # DSL codegen drift check
pnpm e2e                       # Playwright E2E gate
```

See `CLAUDE-PLAN.md` §11 for the phase-by-phase build order. Each phase is gated by an
end-to-end test that must pass before the next phase starts.
