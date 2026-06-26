# syntax=docker/dockerfile:1
# Calypr API — FastAPI + the LangGraph engine. Built from the *repo root* as a uv workspace:
# calypr-api depends on the local calypr-runtime / calypr-codegen packages (and their deps),
# so the whole workspace must be present at build time. See /.dockerignore for what's excluded.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . /app

# Install only the API package + its workspace deps, frozen to uv.lock, without dev deps.
RUN uv sync --frozen --no-dev --package calypr-api

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
# Railway (and most PaaS) inject $PORT; default to 8000 for local `docker run`.
CMD ["sh", "-c", "uvicorn calypr_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
