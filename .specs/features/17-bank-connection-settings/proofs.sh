#!/usr/bin/env bash
# Proofs for spec 17 that are commands rather than single tests. Usage: bash proofs.sh c13 [c18 ...]
#   c13, c18, c35, c49: e2e/bank-settings.spec.ts in the running app, through the Plaid sandbox.
#        Needs frontend/.env.local and services/core/.env.local (Clerk and Plaid sandbox keys)
#   c26, c48: the API against the real Plaid sandbox. Exports services/core/.env.local
#   c53: the generated files match the API, and carry the new routes and status enum
#   c54: every AGENTS.md check for the API and the web app
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
FE="$ROOT/frontend"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

e2e() {
  (cd "$FE" && npx playwright test e2e/bank-settings.spec.ts -g "$2 " --reporter=line) \
    || fail "$1" "the e2e test $2 failed"
  pass "$1"
}

sandbox() {
  (cd "$CORE" && set -a && . ./.env.local && set +a \
    && uv run pytest -m plaid_sandbox tests/test_bank_connection_settings_sandbox.py -k "$2" -q -p no:logging) \
    || fail "$1" "the sandbox proof $2 failed"
  pass "$1"
}

c53() {
  (cd "$CORE" && uv run python -m app.export_openapi) || fail c53 "export failed"
  (cd "$FE" && npm run api:types --silent) || fail c53 "api:types failed"
  git -C "$ROOT" diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts \
    || fail c53 "the generated files are out of date"
  (cd "$ROOT" && python3 - <<'PYEOF') || fail c53 "the contract is missing a route or the status enum"
import json
spec = json.load(open("contracts/openapi.json", encoding="utf-8"))
base = "/v1/businesses/{business_id}/bank/connections/{connection_id}"
assert "post" in spec["paths"][f"{base}/link-token"]
assert "post" in spec["paths"][f"{base}/repair"]
assert "delete" in spec["paths"][base]
props = spec["components"]["schemas"]["Connection"]["properties"]
assert props["status"]["enum"] == ["syncing", "synced", "login_required", "sync_failing"]
assert {"type": "null"} in props["last_synced_at"]["anyOf"]
PYEOF
  pass c53
}

c54() {
  (cd "$CORE" && uv run ruff format --check . && uv run ruff check . && uv run mypy app \
    && uv run pytest -q -p no:logging) || fail c54 "an API check failed"
  (cd "$FE" && npm run lint && npm run typecheck && npm test && npm run build) \
    || fail c54 "a web check failed"
  pass c54
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c13|c18|c26|c35|c48|c49|c53|c54 ..." >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c13) e2e c13 C13 ;;
    c18) e2e c18 C18 ;;
    c35) e2e c35 C35 ;;
    c49) e2e c49 C49 ;;
    c26) sandbox c26 test_sandbox_login_required ;;
    c48) sandbox c48 test_sandbox_disconnect ;;
    c53) c53 ;;
    c54) c54 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
