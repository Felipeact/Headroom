#!/usr/bin/env bash
# Proofs for spec 21 that are commands rather than single tests. Usage: bash proofs.sh c43 [c44]
#   c43: the generated files match the API, and the contract has the forecast routes
#   c44: every AGENTS.md check for the API and the web app
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
FE="$ROOT/frontend"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c43() {
  (cd "$CORE" && uv run python -m app.export_openapi) || fail c43 "export failed"
  (cd "$FE" && npm run api:types --silent) || fail c43 "api:types failed"
  git -C "$ROOT" diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts \
    || fail c43 "the generated files are out of date"
  (cd "$ROOT" && python3 - <<'PYEOF') || fail c43 "the contract is missing a forecast route"
import json
paths = json.load(open("contracts/openapi.json", encoding="utf-8"))["paths"]
forecast = paths["/v1/businesses/{business_id}/forecast"]
upcoming = paths["/v1/businesses/{business_id}/upcoming"]
assert "get" in forecast, sorted(forecast)
assert "get" in upcoming, sorted(upcoming)
days = [p for p in upcoming["get"]["parameters"] if p["name"] == "days"]
assert len(days) == 1 and days[0]["in"] == "query", days
assert days[0]["schema"]["type"] == "integer", days[0]
PYEOF
  pass c43
}

c44() {
  (cd "$CORE" && uv run ruff format --check . && uv run ruff check . && uv run mypy app \
    && uv run pytest -q -p no:logging) || fail c44 "an API check failed"
  (cd "$FE" && npm run lint && npm run typecheck && npm test && npm run build) \
    || fail c44 "a web check failed"
  pass c44
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c43|c44 ..." >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c43) c43 ;;
    c44) c44 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
