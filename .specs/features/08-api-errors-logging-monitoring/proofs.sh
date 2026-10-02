#!/usr/bin/env bash
# Proofs for spec 08 that need Sentry, Railway or GitHub. Usage: bash proofs.sh c21 [c22 c32]
# Each function exits non-zero on failure and prints "PASS cN" on success.
# Sentry is read through its events API with SENTRY_AUTH_TOKEN (scope project:read),
# SENTRY_ORG and SENTRY_PROJECT from the shell; SENTRY_API_URL defaults to https://sentry.io.
# Prints event IDs and pass/fail only, never the DSN or a token.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 1
ENV=staging
SENTRY_API_URL="${SENTRY_API_URL:-https://sentry.io}"

fail() { echo "FAIL $1: $2" >&2; exit 1; }

# json CODE [ARGS...]: run CODE with the parsed stdin bound to d; ARGS land in sys.argv[1:].
json() { python3 -c "import json,sys; d=json.load(sys.stdin); $1" "${@:2}" | tr -d '\r'; }

need_sentry_api() {
  for var in SENTRY_AUTH_TOKEN SENTRY_ORG SENTRY_PROJECT; do
    [ -n "${!var:-}" ] || fail "$1" "$var is not set in this shell"
  done
}

# sentry_environment_of ID: the event's environment tag, polling up to 60 s while Sentry ingests it.
sentry_environment_of() {
  local id="$1" body status deadline=$((SECONDS + 60))
  while [ "$SECONDS" -lt "$deadline" ]; do
    body="$(curl -s -w '\n%{http_code}' \
      -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
      "$SENTRY_API_URL/api/0/projects/$SENTRY_ORG/$SENTRY_PROJECT/events/$id/")"
    status="${body##*$'\n'}"
    if [ "$status" = "200" ]; then
      printf '%s' "${body%$'\n'*}" | json "print(next((t['value'] for t in d.get('tags', []) if t['key']=='environment'), ''))"
      return 0
    fi
    sleep 5
  done
  echo ""
}

is_event_id() { [[ "$1" =~ ^[0-9a-f]{32}$ ]]; }

c21() {
  need_sentry_api c21
  local id environment
  id="$(cd services/core && uv run python -m app.sentry_check | tr -d '\r' | tail -1)" \
    || fail c21 "app.sentry_check exited non-zero"
  is_event_id "$id" || fail c21 "app.sentry_check printed no event ID"
  echo "event $id"
  environment="$(sentry_environment_of "$id")"
  [ "$environment" = "local" ] || fail c21 "event $id not found with environment local (got '$environment')"
  echo "PASS c21"
}

c22() {
  need_sentry_api c22
  local id environment
  id="$(railway ssh --service api --environment "$ENV" -- python -m app.sentry_check 2>/dev/null | tr -d '\r' | tail -1)" \
    || fail c22 "app.sentry_check exited non-zero on staging"
  is_event_id "$id" || fail c22 "app.sentry_check on staging printed no event ID"
  echo "event $id"
  environment="$(sentry_environment_of "$id")"
  [ "$environment" = "staging" ] || fail c22 "event $id not found with environment staging (got '$environment')"
  echo "PASS c22"
}

c32() {
  local sha conclusion
  sha="$(git rev-parse HEAD)"
  [ "$(git rev-parse origin/development)" = "$sha" ] || fail c32 "HEAD is not pushed to origin/development"
  conclusion="$(gh run list --commit "$sha" --workflow CI --json databaseId --jq '.[0].databaseId' \
    | xargs -I{} gh run view {} --json jobs --jq '.jobs[] | select(.name=="api") | .conclusion')"
  [ "$conclusion" = "success" ] || fail c32 "CI job api for $sha concluded '$conclusion'"
  echo "PASS c32"
}

[ "$#" -gt 0 ] || { echo "usage: bash $0 c21 [c22 c32]" >&2; exit 2; }
for check in "$@"; do "$check"; done
