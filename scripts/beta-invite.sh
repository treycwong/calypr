#!/usr/bin/env bash
# Add people to the beta invite list.
#
#   CALYPR_ADMIN_TOKEN=xxxx ./scripts/beta-invite.sh ada@example.com grace@example.com
#   CALYPR_ADMIN_TOKEN=xxxx ./scripts/beta-invite.sh < emails.txt      # one address per line
#
# Against production:
#   CALYPR_API_URL=https://api.calypr.co CALYPR_ADMIN_TOKEN=xxxx ./scripts/beta-invite.sh ada@x.com
#
# Being on the invite list is what flips someone to `beta` — automatically, the next time they
# sign in with that address. Nothing to look up, and re-running is safe.
set -euo pipefail

API_URL="${CALYPR_API_URL:-http://localhost:8000}"

if [[ -z "${CALYPR_ADMIN_TOKEN:-}" ]]; then
  echo "CALYPR_ADMIN_TOKEN is not set." >&2
  echo "It's a password you choose — generate one with: openssl rand -hex 32" >&2
  echo "Then set the same value on the API server (Railway -> Variables)." >&2
  exit 1
fi

# Addresses from the command line, or from stdin when none were given.
# (A read loop rather than `mapfile` — macOS still ships bash 3.2, which doesn't have it.)
emails=()
if [[ $# -gt 0 ]]; then
  emails=("$@")
else
  while IFS= read -r line; do
    [[ -n "${line// /}" ]] && emails+=("$line")
  done
fi

if [[ ${#emails[@]} -eq 0 ]]; then
  echo "No email addresses given." >&2
  echo "Usage: $0 ada@example.com [more@example.com ...]" >&2
  exit 1
fi

payload="$(printf '%s\n' "${emails[@]}" | python3 -c '
import json, sys
print(json.dumps({"emails": [line.strip() for line in sys.stdin if line.strip()]}))
')"

# Capture the response first so a failed request reports cleanly instead of feeding an empty
# body into the parser below. curl's exit code distinguishes "the server said no" (22, with -f)
# from "we never reached the server" — very different problems, so don't report them alike.
# `|| code=$?` rather than `if ! ...`, because inside `if ! cmd` the negation has already
# replaced curl's exit status by the time you read `$?`.
code=0
response="$(curl -fsS -X POST "${API_URL}/admin/invite" \
  -H "x-admin-token: ${CALYPR_ADMIN_TOKEN}" \
  -H "content-type: application/json" \
  -d "$payload")" || code=$?
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

printf '%s' "$response" | python3 -c '
import json, sys
r = json.load(sys.stdin)
for e in r.get("invited", []):
    print(f"  invited        {e}")
for e in r.get("already_invited", []):
    print(f"  already on it  {e}")
print()
print("They get beta automatically the next time they sign in with that address.")
'
