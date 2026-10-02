#!/usr/bin/env bash
# Proofs for spec 07 that need Sentry. Usage: bash proofs.sh c37 [c38]
# Needs NEXT_PUBLIC_SENTRY_DSN in frontend/.env.local (the headroom-web project), and in this
# shell SENTRY_AUTH_TOKEN (scope project:read, event:read), SENTRY_ORG and SENTRY_PROJECT
# (headroom-web). SENTRY_API_URL defaults to https://sentry.io; US-region orgs may need
# https://us.sentry.io. Stop any server on port 3000 first: Playwright reuses it.
# Prints the run nonce and pass/fail only, never the DSN or a token.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT/frontend" || exit 1
SENTRY_API_URL="${SENTRY_API_URL:-https://sentry.io}"

fail() { echo "FAIL $1: $2" >&2; exit 1; }

need_sentry_api() {
  for var in SENTRY_AUTH_TOKEN SENTRY_ORG SENTRY_PROJECT; do
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

# event_count MESSAGE: how many error events in the project carry MESSAGE, polling up to 60 s.
event_count() {
  local message="$1" project_id count deadline=$((SECONDS + 60))
  project_id="$(curl -s -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
    "$SENTRY_API_URL/api/0/projects/$SENTRY_ORG/$SENTRY_PROJECT/" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin).get("id",""))' | tr -d '\r')"
  [ -n "$project_id" ] || { echo 0; return; }
  while [ "$SECONDS" -lt "$deadline" ]; do
    count="$(curl -s -G -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
      "$SENTRY_API_URL/api/0/organizations/$SENTRY_ORG/events/" \
      --data-urlencode "dataset=errors" \
      --data-urlencode "field=id" \
      --data-urlencode "field=message" \
      --data-urlencode "project=$project_id" \
      --data-urlencode "statsPeriod=1h" \
      --data-urlencode "query=message:\"$message\"" \
      | python3 -c 'import json,sys; print(len(json.load(sys.stdin).get("data",[])))' 2>/dev/null | tr -d '\r')"
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
