#!/usr/bin/env bash
# Proofs for spec 13 that are commands rather than single tests. Usage: bash proofs.sh c31 [c51 ...]
#   c31: two banks on one business through the real Plaid sandbox. Exports services/core/.env.local
#   c51: spec 12's step 3 e2e and the existing e2e specs, now that step 3 lands on choose accounts
#   c52: the generated files match the API
#   c53: every AGENTS.md check for the API and the web app
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
FE="$ROOT/frontend"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c31() {
  (cd "$CORE" && set -a && . ./.env.local && set +a \
    && uv run pytest -m plaid_sandbox tests/test_bank_accounts_sandbox.py -q -p no:logging) \
    || fail c31 "the two-bank sandbox proof failed"
  pass c31
}

c51() {
  (cd "$FE" && npx playwright test e2e/bank-connect.spec.ts e2e/onboarding.spec.ts \
    e2e/shell.spec.ts e2e/home.spec.ts e2e/auth.spec.ts e2e/api-check.spec.ts --reporter=line) \
    || fail c51 "an existing e2e spec failed"
  pass c51
}

c52() {
  (cd "$CORE" && uv run python -m app.export_openapi) || fail c52 "export failed"
  (cd "$FE" && npm run api:types --silent) || fail c52 "api:types failed"
  git -C "$ROOT" diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts \
    || fail c52 "the generated files are out of date"
  for path in "/v1/businesses/{business_id}/bank/connections" \
    "/v1/businesses/{business_id}/bank/accounts/{account_id}"; do
    grep -qF "\"$path\"" "$ROOT/contracts/openapi.json" || fail c52 "missing $path"
  done
  grep -qF '"patch"' "$ROOT/contracts/openapi.json" || fail c52 "missing the PATCH operation"
  pass c52
}

c53() {
  (cd "$CORE" && uv run ruff format --check . && uv run ruff check . && uv run mypy app \
    && uv run pytest -q -p no:logging) || fail c53 "an API check failed"
  (cd "$FE" && npm run lint && npm run typecheck && npm test && npm run build) \
    || fail c53 "a web check failed"
  pass c53
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c31|c51|c52|c53 ..." >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c31) c31 ;;
    c51) c51 ;;
    c52) c52 ;;
    c53) c53 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
