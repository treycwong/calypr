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

pnpm dev                       # web app  → http://localhost:3000
uv run --project apps/api uvicorn calypr_api.main:app --reload   # api → http://localhost:8000
```

### Tests

```bash
uv run pytest                  # backend (api + dsl)
pnpm --filter @calypr/dsl gen:check   # DSL codegen drift check
pnpm e2e                       # Playwright E2E gate
```

See `CLAUDE-PLAN.md` §11 for the phase-by-phase build order. Each phase is gated by an
end-to-end test that must pass before the next phase starts.
