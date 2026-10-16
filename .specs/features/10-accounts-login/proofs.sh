#!/usr/bin/env bash
# Proofs for spec 10 that are commands rather than single tests. Usage: bash proofs.sh c15 [c20 ...]
#   c20: run after `npx playwright test e2e/auth.spec.ts -g "shows the name"`; reads the test
#        user's Clerk ID with CLERK_SECRET_KEY and E2E_CLERK_USER_USERNAME from
#        frontend/.env.local, and the database through services/core settings
#   c33: C33_SHA = the feature commit pushed to development (default: origin/development)
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
FE="$ROOT/frontend"
CORE="$ROOT/services/core"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c15() {
  local dir="$CORE/app/modules/accounts" f
  for f in api.py service.py models.py repository.py; do
    [ -f "$dir/$f" ] || fail c15 "missing app/modules/accounts/$f"
  done
  (cd "$CORE" && uv run python -c "
import sys
from app.modules.accounts import service
sys.exit(0 if (service.get_or_create_user.__doc__ or '').strip() else 1)") \
    || fail c15 "service.get_or_create_user has no docstring"
  if grep -En '^\s*(from|import)\s+app\.modules\.' "$dir"/*.py | grep -Ev 'app\.modules\.accounts([. ]|$)'; then
    fail c15 "accounts imports another module"
  fi
  pass c15
}

env_value() { grep -E "^$1=" "$FE/.env.local" | head -1 | cut -d= -f2- | tr -d '\r'; }

c20() {
  local sk user id rows
  sk="$(env_value CLERK_SECRET_KEY)"; user="$(env_value E2E_CLERK_USER_USERNAME)"
  [ -n "$sk" ] && [ -n "$user" ] || fail c20 "CLERK_SECRET_KEY or E2E_CLERK_USER_USERNAME missing"
  id="$(curl -s -H "Authorization: Bearer $sk" "https://api.clerk.com/v1/users?username=$user" \
    | python3 -c "import json,sys; u=json.load(sys.stdin); print(u[0]['id'] if len(u)==1 else '')" | tr -d '\r')"
  [ -n "$id" ] || fail c20 "could not read the test user's Clerk ID"
  rows="$(cd "$CORE" && uv run python -c "
import sys
from sqlalchemy import func, select
from app.db import get_sessionmaker
from app.modules.accounts.models import User
with get_sessionmaker()() as s:
    print(s.scalar(select(func.count()).select_from(User).where(User.clerk_user_id == sys.argv[1])))
" "$id" | tr -d '\r')"
  [ "$rows" = "1" ] || fail c20 "expected 1 users row for the test user, found '$rows'"
  pass c20
}

c31() {
  local hits
  hits="$(cd "$ROOT" && git ls-files -co --exclude-standard frontend | grep -Ev '(^|/)node_modules/' \
    | xargs grep -l 'getToken' 2>/dev/null | grep -Ev '^frontend/tests/')"
  [ "$hits" = "frontend/lib/api/auth.ts" ] || fail c31 "getToken appears in: ${hits:-nothing}"
  if grep -En 'console\.|cookies\(|localStorage|sessionStorage' "$FE/lib/api/auth.ts"; then
    fail c31 "lib/api/auth.ts logs or stores something"
  fi
  pass c31
}

c32() {
  local line
  for line in 'NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=' 'CLERK_SECRET_KEY=' \
    'NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in' 'NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up'; do
    grep -qxF "$line" "$FE/.env.example" || fail c32 "frontend/.env.example lacks '$line'"
  done
  for line in 'CLERK_JWT_KEY=' 'CLERK_AUTHORIZED_PARTIES='; do
    grep -qxF "$line" "$CORE/.env.example" || fail c32 "services/core/.env.example lacks '$line'"
  done
  # Tracked files plus untracked files git would add; .env.local is ignored by design.
  local leaks
  leaks="$(cd "$ROOT" && git ls-files -co --exclude-standard -z \
    | xargs -0 grep -lE '(sk|pk)_(test|live)_[A-Za-z0-9]{20,}|-----BEGIN (RSA )?(PUBLIC|PRIVATE) KEY-----' 2>/dev/null)"
  [ -z "$leaks" ] || fail c32 "key material in: $leaks"
  pass c32
}

run_jobs() {
  local sha="$1" id status
  for _ in $(seq 1 120); do
    id="$(gh run list --commit "$sha" --workflow CI --limit 1 --json databaseId --jq '.[0].databaseId' | tr -d '\r')"
    if [ -n "$id" ]; then
      status="$(gh run view "$id" --json status --jq .status | tr -d '\r')"
      [ "$status" = "completed" ] && { gh run view "$id" --json jobs; return 0; }
    fi
    sleep 10
  done
  return 1
}

jobs_py() { python3 -c "import json,sys; jobs=json.load(sys.stdin)['jobs']; $1" "${@:2}" | tr -d '\r'; }
job_conclusion() { jobs_py "print(next(j['conclusion'] for j in jobs if j['name']==sys.argv[1]))" "$2" <<<"$1"; }
job_names() { jobs_py "print(','.join(sorted(j['name'] for j in jobs)))" <<<"$1"; }

c33() {
  local sha="${C33_SHA:-$(git rev-parse origin/development)}"
  local jobs; jobs="$(run_jobs "$sha")" || fail c33 "no finished CI run for $sha"
  [ "$(job_names "$jobs")" = "api,web" ] || fail c33 "job names are not exactly web and api"
  [ "$(job_conclusion "$jobs" web)" = "success" ] || fail c33 "web did not succeed"
  [ "$(job_conclusion "$jobs" api)" = "success" ] || fail c33 "api did not succeed"
  pass c33
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c15 [c20 ...]" >&2; exit 2; }
for check in "$@"; do "$check"; done
