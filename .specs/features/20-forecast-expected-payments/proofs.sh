#!/usr/bin/env bash
# Proofs for spec 20 that are commands rather than single tests. Usage: bash proofs.sh c16 [c47]
#   c16: the generated files match the API, and the contract has the expected payments routes
#   c47: every AGENTS.md check for the API and the web app
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
FE="$ROOT/frontend"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c16() {
  (cd "$CORE" && uv run python -m app.export_openapi) || fail c16 "export failed"
  (cd "$FE" && npm run api:types --silent) || fail c16 "api:types failed"
  git -C "$ROOT" diff --exit-code -- contracts/openapi.json frontend/lib/api/schema.d.ts \
    || fail c16 "the generated files are out of date"
  (cd "$ROOT" && python3 - <<'PYEOF') || fail c16 "the contract is missing an expected payments route"
import json
paths = json.load(open("contracts/openapi.json", encoding="utf-8"))["paths"]
collection = paths["/v1/businesses/{business_id}/expected-payments"]
item = paths["/v1/businesses/{business_id}/expected-payments/{payment_id}"]
assert {"get", "post"} <= set(collection), sorted(collection)
assert {"put", "delete"} <= set(item), sorted(item)
PYEOF
  pass c16
}

c47() {
  (cd "$CORE" && uv run ruff format --check . && uv run ruff check . && uv run mypy app \
    && uv run pytest -q -p no:logging) || fail c47 "an API check failed"
  (cd "$FE" && npm run lint && npm run typecheck && npm test && npm run build) \
    || fail c47 "a web check failed"
  pass c47
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c16|c47 ..." >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c16) c16 ;;
    c47) c47 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
