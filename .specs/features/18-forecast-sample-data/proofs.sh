#!/usr/bin/env bash
# Proofs for spec 18 that are commands rather than single tests. Usage: bash proofs.sh c36 [c37]
#   c36: the generated files match the API, and the contract has the transactions route
#   c37: every AGENTS.md check for the API and the web app
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
FE="$ROOT/frontend"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c36() {
  (cd "$CORE" && uv run python -m app.export_openapi) || fail c36 "export failed"
  (cd "$FE" && npm run api:types --silent) || fail c36 "api:types failed"
  git -C "$ROOT" diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts \
    || fail c36 "the generated files are out of date"
  (cd "$ROOT" && python3 - <<'PYEOF') || fail c36 "the contract is missing the transactions route"
import json
spec = json.load(open("contracts/openapi.json", encoding="utf-8"))
assert "get" in spec["paths"]["/v1/businesses/{business_id}/bank/transactions"]
PYEOF
  pass c36
}

c37() {
  (cd "$CORE" && uv run ruff format --check . && uv run ruff check . && uv run mypy app \
    && uv run pytest -q -p no:logging) || fail c37 "an API check failed"
  (cd "$FE" && npm run lint && npm run typecheck && npm test && npm run build) \
    || fail c37 "a web check failed"
  pass c37
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c36|c37 ..." >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c36) c36 ;;
    c37) c37 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
