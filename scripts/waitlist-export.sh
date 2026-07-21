#!/usr/bin/env bash
# Export the waitlist to a CSV you can open in Excel / Google Sheets.
#
#   CALYPR_ADMIN_TOKEN=xxxx ./scripts/waitlist-export.sh                 # -> waitlist.csv
#   CALYPR_ADMIN_TOKEN=xxxx ./scripts/waitlist-export.sh partners.csv    # custom filename
#
# Point it at another environment with CALYPR_API_URL:
#   CALYPR_API_URL=https://api.calypr.co CALYPR_ADMIN_TOKEN=xxxx ./scripts/waitlist-export.sh
set -euo pipefail

API_URL="${CALYPR_API_URL:-http://localhost:8000}"
OUT="${1:-waitlist.csv}"

if [[ -z "${CALYPR_ADMIN_TOKEN:-}" ]]; then
  echo "CALYPR_ADMIN_TOKEN is not set." >&2
  echo "It's a password you choose — generate one with: openssl rand -hex 32" >&2
  echo "Then set the same value on the API server (Railway -> Variables)." >&2
  exit 1
fi

response="$(curl -fsS "${API_URL}/admin/waitlist" -H "x-admin-token: ${CALYPR_ADMIN_TOKEN}")" || {
  echo "Request failed. A 404 usually means CALYPR_ADMIN_TOKEN is unset on the server," >&2
  echo "or doesn't match the one you passed here (the admin routes fail closed)." >&2
  exit 1
}

# Emit CSV via python3 so quoting/escaping is handled properly (no jq dependency).
printf '%s' "$response" | python3 -c '
import csv, json, sys
rows = json.load(sys.stdin)
w = csv.writer(sys.stdout)
w.writerow(["email", "source", "signed_up_at", "invited_at"])
for r in rows:
    w.writerow([r.get("email", ""), r.get("source", ""), r.get("created_at", ""), r.get("invited_at") or ""])
' > "$OUT"

echo "Wrote $(( $(wc -l < "$OUT") - 1 )) signups to ${OUT}"
