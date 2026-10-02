#!/usr/bin/env bash
# Proofs for spec 07 that need Sentry. Usage: bash proofs.sh c37 [c38]
# Needs NEXT_PUBLIC_SENTRY_DSN in frontend/.env.local (the headroom-web project), and in this
# shell SENTRY_ORG, SENTRY_PROJECT (headroom-web) and a token that can read events:
# SENTRY_READ_TOKEN (a personal sntryu_ token with project:read and event:read). An
# organization token (sntrys_, used for source maps) gets 403 from these endpoints.
# Load them with: set -a; . frontend/.env.local; set +a
# SENTRY_API_URL defaults to https://sentry.io; US-region orgs may need
# https://us.sentry.io. Stop any server on port 3000 first: Playwright reuses it.
# Prints the run nonce and pass/fail only, never the DSN or a token.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT/frontend" || exit 1
SENTRY_API_URL="${SENTRY_API_URL:-https://sentry.io}"

fail() { echo "FAIL $1: $2" >&2; exit 1; }

need_sentry_api() {
  for var in SENTRY_READ_TOKEN SENTRY_ORG SENTRY_PROJECT; do
    [ -n "${!var:-}" ] || fail "$1" "$var is not set in this shell"
  done
  grep -q '^NEXT_PUBLIC_SENTRY_DSN=..*' .env.local 2>/dev/null \
    || fail "$1" "NEXT_PUBLIC_SENTRY_DSN is not set in frontend/.env.local"
}

# Clicks both buttons once per script run, tagged with a fresh nonce.
RUN_ID=""
click_buttons() {
  [ -n "$RUN_ID" ] && return 0
  RUN_ID="check$(date +%s)$RANDOM"
  echo "run $RUN_ID"
  SENTRY_CHECK_RUN="$RUN_ID" npx playwright test e2e/sentry-check.spec.ts --reporter=line >/dev/null \
    || fail "$1" "the sentry-check Playwright run failed"
}

# event_count MESSAGE: how many issues in the project, seen in the last 24 h, have a title
# containing MESSAGE, polling up to 60 s. Uses the project issues endpoint, which needs only
# project:read and event:read; the org-wide events endpoint also needs org:read.
event_count() {
  local message="$1" count deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    count="$(curl -s -G -H "Authorization: Bearer $SENTRY_READ_TOKEN"       "$SENTRY_API_URL/api/0/projects/$SENTRY_ORG/$SENTRY_PROJECT/issues/"       --data-urlencode "statsPeriod=24h"       --data-urlencode "query=\"$message\""       | python3 -c 'import json,sys
m=sys.argv[1]; d=json.load(sys.stdin)
print(sum(1 for i in d if m in (i.get("title") or "")) if isinstance(d,list) else 0)' "$message" 2>/dev/null | tr -d '')"
    [ "${count:-0}" -gt 0 ] && { echo "$count"; return; }
    sleep 5
  done
  echo 0
}

c37() {
  need_sentry_api c37
  click_buttons c37
  [ "$(event_count "Headroom web Sentry check (client) $RUN_ID")" -gt 0 ] \
    || fail c37 "no client event for run $RUN_ID in $SENTRY_PROJECT"
  echo "PASS c37"
}

c38() {
  need_sentry_api c38
  click_buttons c38
  [ "$(event_count "Headroom web Sentry check (server) $RUN_ID")" -gt 0 ] \
    || fail c38 "no server event for run $RUN_ID in $SENTRY_PROJECT"
  echo "PASS c38"
}

[ "$#" -gt 0 ] || { echo "usage: bash $0 c37 [c38]" >&2; exit 2; }
for proof in "$@"; do
  case "$proof" in
    c37 | c38) "$proof" ;;
    *) fail "$proof" "unknown proof" ;;
  esac
done
