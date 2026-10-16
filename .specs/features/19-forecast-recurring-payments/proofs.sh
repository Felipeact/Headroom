#!/usr/bin/env bash
# Proofs for spec 19 that are commands rather than single tests. Usage: bash proofs.sh c32 [c33]
#   c32: the generated files match the API, and the contract has the recurring patterns route
#   c33: every AGENTS.md check for the API and the web app
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
FE="$ROOT/frontend"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c32() {
  (cd "$CORE" && uv run python -m app.export_openapi) || fail c32 "export failed"
  (cd "$FE" && npm run api:types --silent) || fail c32 "api:types failed"
  git -C "$ROOT" diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts \
    || fail c32 "the generated files are out of date"
  (cd "$ROOT" && python3 - <<'PYEOF') || fail c32 "the contract is missing the recurring patterns route"
import json
spec = json.load(open("contracts/openapi.json", encoding="utf-8"))
assert "get" in spec["paths"]["/v1/businesses/{business_id}/recurring-patterns"]
PYEOF
  pass c32
}

c33() {
  (cd "$CORE" && uv run ruff format --check . && uv run ruff check . && uv run mypy app \
    && uv run pytest -q -p no:logging) || fail c33 "an API check failed"
  (cd "$FE" && npm run lint && npm run typecheck && npm test && npm run build) \
    || fail c33 "a web check failed"
  pass c33
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c32|c33 ..." >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c32) c32 ;;
    c33) c33 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
