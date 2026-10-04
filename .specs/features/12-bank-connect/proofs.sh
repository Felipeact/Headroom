#!/usr/bin/env bash
# Proofs for spec 12 that are commands rather than single tests. Usage: bash proofs.sh c21 [c44 ...]
#   c21: the real Plaid sandbox. Exports services/core/.env.local (sandbox keys, local Postgres)
#   c44: the spec 11 onboarding specs and the existing e2e specs, now that step 2 lands on step 3
#   c45: the generated files match the API
#   c46: every AGENTS.md check for the API and the web app
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
FE="$ROOT/frontend"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c21() {
  (cd "$CORE" && set -a && . ./.env.local && set +a \
    && uv run pytest -m plaid_sandbox tests/test_bank_connect_sandbox.py -q -p no:logging) \
    || fail c21 "the sandbox connection failed"
  pass c21
}

c44() {
  (cd "$FE" && npx playwright test e2e/onboarding.spec.ts e2e/shell.spec.ts e2e/home.spec.ts \
    e2e/auth.spec.ts e2e/api-check.spec.ts --grep-invert "C42" --reporter=line) \
    || fail c44 "an existing e2e spec failed"
  pass c44
}

c45() {
  (cd "$CORE" && uv run python -m app.export_openapi) || fail c45 "export failed"
  (cd "$FE" && npm run api:types --silent) || fail c45 "api:types failed"
  git -C "$ROOT" diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts \
    || fail c45 "the generated files are out of date"
  for path in "/v1/businesses/{business_id}/bank/link-token" \
    "/v1/businesses/{business_id}/bank/connections"; do
    grep -qF "\"$path\"" "$ROOT/contracts/openapi.json" || fail c45 "missing $path"
  done
  pass c45
}

c46() {
  (cd "$CORE" && uv run ruff format --check . && uv run ruff check . && uv run mypy app \
    && uv run pytest -q -p no:logging) || fail c46 "an API check failed"
  (cd "$FE" && npm run lint && npm run typecheck && npm test && npm run build) \
    || fail c46 "a web check failed"
  pass c46
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c21|c44|c45|c46 ..." >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c21) c21 ;;
    c44) c44 ;;
    c45) c45 ;;
    c46) c46 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
