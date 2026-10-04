#!/usr/bin/env bash
# Proofs for spec 11 that are commands rather than single tests. Usage: bash proofs.sh c39
#   c39: the existing e2e specs that need the test user to have a business. Needs the local
#        Postgres at Alembic head and frontend/.env.local (Clerk keys, E2E_CLERK_USER_USERNAME)
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
FE="$ROOT/frontend"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c39() {
  (cd "$FE" && npx playwright test e2e/shell.spec.ts e2e/home.spec.ts e2e/auth.spec.ts \
    e2e/api-check.spec.ts --grep-invert "C42" --reporter=line) \
    || fail c39 "an existing e2e spec failed"
  pass c39
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c39" >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c39) c39 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
