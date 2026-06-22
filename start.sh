#!/usr/bin/env bash
#
# Start Calypr locally — the FastAPI engine + the Next.js canvas, together.
# Ctrl-C stops both. Override ports with API_PORT / WEB_PORT, e.g.:
#   API_PORT=8000 WEB_PORT=3100 ./start.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-3100}"
# The web's Next route proxies server-side to the API at this URL.
export CALYPR_API_URL="http://localhost:${API_PORT}"

# Make sure pnpm is on PATH (Corepack ships with Node ≥ 20).
command -v pnpm >/dev/null 2>&1 || corepack enable >/dev/null 2>&1 || true

# Best-effort Postgres. Only needed to *save* agents — chat + the Code view work without it.
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  printf '▸ Postgres (docker)… '
  if docker compose -f infra/docker/compose.yaml up -d --wait >/dev/null 2>&1; then
    echo "up"
  else
    echo "skipped (Save unavailable; chat still works)"
  fi
else
  echo "▸ Docker not running — skipping Postgres (Save unavailable; chat still works)"
fi

pids=()
cleaned=0
cleanup() {
  [ "$cleaned" = 1 ] && return
  cleaned=1
  echo ""
  echo "▸ Stopping…"
  for pid in "${pids[@]}"; do kill "$pid" >/dev/null 2>&1 || true; done
  wait >/dev/null 2>&1 || true
}
trap cleanup INT TERM EXIT

echo "▸ API  → http://localhost:${API_PORT}   (uvicorn --reload, auto-loads .env)"
uv run uvicorn calypr_api.main:app --reload --port "${API_PORT}" &
pids+=("$!")

echo "▸ Web  → http://localhost:${WEB_PORT}   (next dev)"
pnpm --filter @calypr/web exec next dev --port "${WEB_PORT}" &
pids+=("$!")

echo ""
echo "✅ Calypr starting → open http://localhost:${WEB_PORT}  (sign in → Open canvas)"
echo "   Ctrl-C to stop both."
wait
