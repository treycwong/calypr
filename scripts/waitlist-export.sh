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

# curl's exit code separates "the server said no" (22, with -f) from "we never reached it".
# `|| code=$?` rather than `if ! ...`, because inside `if ! cmd` the negation has already
# replaced curl's exit status by the time you read `$?`.
code=0
response="$(curl -fsS "${API_URL}/admin/waitlist" -H "x-admin-token: ${CALYPR_ADMIN_TOKEN}")" || code=$?
if [[ $code -ne 0 ]]; then
  if [[ $code -eq 22 ]]; then
    echo "The server rejected the request. A 404 here means CALYPR_ADMIN_TOKEN is unset on the" >&2
    echo "server, or doesn't match the one you passed (the admin routes fail closed)." >&2
  else
    echo "Couldn't reach ${API_URL} (curl exit ${code}) — the request never got there, so this" >&2
    echo "is a network problem, not an auth one. Things to try:" >&2
    echo "  * curl -4 ${API_URL}/health      (force IPv4 — fixes many 'connection reset' cases)" >&2
    echo "  * a different network / phone hotspot, or off VPN" >&2
    echo "  * some ISPs and corporate networks block *.up.railway.app specifically" >&2
  fi
  exit 1
fi

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
