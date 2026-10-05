#!/usr/bin/env bash
# Proofs for spec 14 that are commands rather than single tests. Usage: bash proofs.sh c39 [c46 ...]
#   c39: C39 and C40 - a real Plaid sandbox item synced twice. Exports services/core/.env.local,
#        which must hold the sandbox PLAID_CLIENT_ID, PLAID_SECRET and TOKEN_ENCRYPTION_KEYS
#   c46: the generated files match the API and carry the webhook route
#   c47: every AGENTS.md check for the API and the web app
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
FE="$ROOT/frontend"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c39() {
  (cd "$CORE" && set -a && . ./.env.local && set +a \
    && uv run pytest -m plaid_sandbox tests/test_transaction_sync_sandbox.py -q -p no:logging) \
    || fail c39 "the sandbox sync proof failed"
  pass c39
}

c46() {
  (cd "$CORE" && uv run python -m app.export_openapi) || fail c46 "export failed"
  (cd "$FE" && npm run api:types --silent) || fail c46 "api:types failed"
  git -C "$ROOT" diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts \
    || fail c46 "the generated files are out of date"
  grep -qF '"/v1/webhooks/plaid"' "$ROOT/contracts/openapi.json" \
    || fail c46 "missing /v1/webhooks/plaid in openapi.json"
  grep -qF '"/v1/webhooks/plaid"' "$FE/lib/api/schema.d.ts" \
    || fail c46 "missing /v1/webhooks/plaid in schema.d.ts"
  pass c46
}

c47() {
  (cd "$CORE" && uv run ruff format --check . && uv run ruff check . && uv run mypy app \
    && uv run pytest -q -p no:logging) || fail c47 "an API check failed"
  (cd "$FE" && npm run lint && npm run typecheck && npm test && npm run build) \
    || fail c47 "a web check failed"
  pass c47
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c39|c46|c47 ..." >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c39) c39 ;;
    c46) c46 ;;
    c47) c47 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
