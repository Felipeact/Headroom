#!/usr/bin/env bash
# Proofs for spec 34 (production). Usage: bash proofs.sh c1 [c2 ...]
# Each function exits non-zero on failure and prints "PASS cN" on success.
# Reads Railway through the CLI with an explicit --environment; never prints variable values.
# C17 needs FOUNDER_EMAIL set to the address the founder signed up with in production.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 1
HERE=".specs/features/34-launch-production"
PROD=production
STAGING=staging
EVIDENCE="$HERE/evidence.md"

fail() { echo "FAIL $1: $2" >&2; exit 1; }

# The IaC SDK checks the CLI version by running "$_ --version"; Git Bash sets $_ to a path
# Node cannot execute on Windows, so point it at the real binary when there is one.
railway_iac() {
  local exe
  exe="$(npm root -g 2>/dev/null)/@railway/cli/bin/railway.exe"
  if [ -f "$exe" ]; then env _="$exe" "$exe" "$@"; else railway "$@"; fi
}

# json CODE [ARGS...]: run CODE with the parsed stdin bound to d; ARGS land in sys.argv[1:].
json() { python3 -c "import json,sys; d=json.load(sys.stdin); $1" "${@:2}" | tr -d '\r'; }

# Production's hostnames are fixed by door 8.
domain_of() { # service
  case "$1" in web) echo headroom.felipeviana.com ;; api) echo api.headroom.felipeviana.com ;; *) return 1 ;; esac
}

deployments() { railway deployment list --service "$1" --environment "${2:-$PROD}" --limit 100 --json; }

latest_success() { # service field
  deployments "$1" | json "x=next((x for x in d if x['status']=='SUCCESS'), None); print('' if x is None else (x['id'] if '$2'=='id' else (x.get('meta') or {}).get('$2','')))"
}

# Variables are compared inside Python and never printed.
variables() { railway variable list --service "$1" --environment "$2" --json; }

# remote ENV CODE: run Python in that environment's api container; prints its last line.
remote() {
  railway ssh --service api --environment "$1" -- python -c "$2" 2>/dev/null | tr -d '\r' | tail -1
}

http_check() { # name url expected_status expected_body
  local out status body
  out="$(curl -sS --max-time 30 -w '\n%{http_code}' "$2")" || fail "$1" "request to $2 failed"
  status="${out##*$'\n'}"; body="${out%$'\n'*}"
  [ "$status" = "$3" ] || fail "$1" "$2 answered $status, expected $3"
  [ -z "$4" ] || [ "$body" = "$4" ] || fail "$1" "$2 body was '$body', expected '$4'"
}

evidence() { # name check-id: the row must exist, carry an ISO date and say confirmed
  [ -f "$EVIDENCE" ] || fail "$1" "$EVIDENCE does not exist"
  grep -E "^\| *$2 *\|" "$EVIDENCE" | grep -E '[0-9]{4}-[0-9]{2}-[0-9]{2}' | grep -qi 'confirmed' \
    || fail "$1" "no dated, confirmed row for $2 in $EVIDENCE"
}

BUSINESS_COUNT='import sys
from sqlalchemy import func, select
from app.db import get_sessionmaker
from app.modules.accounts.models import Business
with get_sessionmaker()() as s:
    print(" ".join(str(s.scalar(select(func.count()).select_from(Business).where(Business.name == n))) for n in ("Restore drill A", "Restore drill B")))'

c1() { http_check c1 "https://$(domain_of api)/healthz/ready" 200 '{"status":"ok"}'; echo "PASS c1"; }

c2() {
  local web; web="$(domain_of web)"
  http_check c2 "https://$web/healthz" 200 '{"status":"ok"}'
  local headers
  headers="$(curl -sS --max-time 30 -D - -o /dev/null "https://$web/")" || fail c2 "request to / failed"
  echo "$headers" | head -1 | grep -q ' 307' || fail c2 "/ did not answer 307"
  echo "$headers" | grep -i '^location:' | grep -q '/sign-in' || fail c2 "/ does not redirect to /sign-in"
  echo "PASS c2"
}

c3() {
  local id current heads
  id="$(latest_success api id)"; [ -n "$id" ] || fail c3 "no SUCCESS production api deployment"
  railway logs "$id" --service api --environment "$PROD" --deployment --lines 1000 | grep -c 'Context impl PostgresqlImpl' >/dev/null \
    || fail c3 "deploy logs of $id do not show alembic running"
  current="$(railway ssh --service api --environment "$PROD" -- alembic current 2>/dev/null | tr -d '\r' | grep -oE '^[0-9a-f]{6,}' | head -1)"
  # The running container holds main's code, so its own `alembic heads` is main's head.
  heads="$(railway ssh --service api --environment "$PROD" -- alembic heads 2>/dev/null | tr -d '\r' | grep -oE '^[0-9a-f]{6,}' | head -1)"
  [ -n "$current" ] && [ "$current" = "$heads" ] || fail c3 "production is at '$current', head is '$heads'"
  echo "PASS c3"
}

c4() {
  local svc id sha
  git fetch -q origin main
  for svc in api web jobs; do
    id="$(railway service list --environment "$PROD" --json | json "print(next(s['id'] for s in d if s['name']=='$svc'))")"
    railway environment config --environment "$PROD" --json | json "assert d['services']['$id']['source']['branch']=='main'" \
      || fail c4 "$svc does not track main"
    for sha in $(deployments "$svc" | json "print('\n'.join(h for h in ((x.get('meta') or {}).get('commitHash') for x in d) if h))"); do
      git merge-base --is-ancestor "$sha" origin/main || fail c4 "$svc deployed $sha, which is not on main"
    done
  done
  echo "PASS c4"
}

c5() {
  local svc main sha
  git fetch -q origin main; main="$(git rev-parse origin/main)"
  for svc in api web; do
    sha="$(latest_success "$svc" commitHash)"
    [ "$sha" = "$main" ] || fail c5 "$svc newest SUCCESS is $sha, origin/main is $main"
    # Railway marks a deployment started by a GitHub push with meta.reason "deploy".
    [ "$(latest_success "$svc" reason)" = deploy ] || fail c5 "$svc newest SUCCESS was not started by a push"
  done
  echo "PASS c5"
}

c6() {
  railway service list --environment "$PROD" --json | json "
names={s['name']:[r['name'] for r in s.get('regions') or []] for s in d}
for n in ('Postgres','api','web','jobs'):
    assert names.get(n) and all(r.startswith('us-east') for r in names[n]), (n, names.get(n))" \
    || fail c6 "a production service is missing or not in us-east"
  railway domain list --service Postgres --environment "$PROD" --json | json "assert d['domains']==[], d" \
    || fail c6 "production Postgres has a public domain"
  railway tcp-proxy list --service Postgres --environment "$PROD" --json | json "assert d['proxies']==[], d" \
    || fail c6 "production Postgres has a TCP proxy"
  echo "PASS c6"
}

c7() {
  local api; api="$(domain_of api)"
  http_check c7 "https://$api/docs" 404 ""
  http_check c7 "https://$api/openapi.json" 404 ""
  echo "PASS c7"
}

c8() {
  local env status=0
  for env in "$PROD" "$STAGING"; do
    railway environment link "$env" >/dev/null || { status=1; break; }
    railway_iac config plan --detailed-exit-code >/dev/null 2>&1 || { echo "FAIL c8: $env differs from .railway/railway.ts" >&2; status=1; }
  done
  railway environment link "$STAGING" >/dev/null
  [ "$status" = 0 ] || exit 1
  echo "PASS c8"
}

c9() { node --no-warnings "$HERE/iac-check.mjs" "$ROOT" c9 || exit 1; }

c10() { node --no-warnings "$HERE/iac-check.mjs" "$ROOT" c10 || exit 1; }

c11() { python3 "$HERE/check_no_shared_credentials.py" || fail c11 "staging and production share a credential"; echo "PASS c11"; }

c16() {
  variables api "$PROD" | json "
import sys
ok = d.get('PLAID_ENV') == 'production' and d.get('API_DOCS_ENABLED', '').lower() != 'true'
print('match' if ok else 'mismatch'); sys.exit(0 if ok else 1)" || fail c16 "PLAID_ENV or API_DOCS_ENABLED"
  echo "PASS c16"
}

c17() {
  [ -n "${FOUNDER_EMAIL:-}" ] || fail c17 "set FOUNDER_EMAIL"
  local code prod staging
  # Prints "<count> <first user id or ->"; the id stays in this script, never in the output.
  code="from clerk_backend_api import Clerk
from app.settings import get_settings
users = Clerk(bearer_auth=get_settings().clerk_secret_key).users.list(request={'email_address': ['$FOUNDER_EMAIL']})
print(len(users), users[0].id if users else '-')"
  prod="$(remote "$PROD" "$code")"; staging="$(remote "$STAGING" "$code")"
  echo "production=${prod%% *} staging=${staging%% *}"
  [ "${prod%% *}" = 1 ] || fail c17 "expected exactly 1 production user"
  case "${staging%% *}" in 0|1) ;; *) fail c17 "expected at most 1 staging user" ;; esac
  [ "${prod#* }" != "${staging#* }" ] || fail c17 "production and staging share a user id"
  echo "ids differ"
  variables web "$PROD" | json "
import sys
ok = d.get('NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY', '').startswith('pk_live_')
print('match' if ok else 'mismatch'); sys.exit(0 if ok else 1)" || fail c17 "production web is not on a pk_live_ key"
  echo "PASS c17"
}

c18() { evidence c18 C18; echo "PASS c18"; }

c19() {
  variables api "$PROD" | json "
import sys
ok = d.get('EMAIL_SENDER') == 'resend' and 'onboarding@resend.dev' in d.get('EMAIL_FROM', '')
print('match' if ok else 'mismatch'); sys.exit(0 if ok else 1)" || fail c19 "EMAIL_SENDER or EMAIL_FROM"
  echo "PASS c19"
}

c20() {
  variables api "$PROD" | json "
import sys
web, api = 'https://headroom.felipeviana.com', 'https://api.headroom.felipeviana.com'
want = {'WEB_URL': web, 'API_PUBLIC_URL': api, 'PLAID_WEBHOOK_URL': api + '/v1/webhooks/plaid', 'CLERK_AUTHORIZED_PARTIES': web}
bad = [k for k, v in want.items() if d.get(k) != v]
print('mismatch: ' + ' '.join(bad) if bad else 'match'); sys.exit(1 if bad else 0)" || fail c20 "production URLs"
  local host
  for host in headroom.felipeviana.com api.headroom.felipeviana.com; do
    curl -sS --max-time 30 -o /dev/null "https://$host/" || fail c20 "https://$host has no valid certificate or does not answer"
  done
  echo "PASS c20"
}

c21() {
  local statuses
  statuses="$(remote "$PROD" "from sqlalchemy import select
from app.db import get_sessionmaker
from app.modules.bank_sync.models import BankConnection
with get_sessionmaker()() as s:
    print(' '.join(sorted({c.last_synced_at is not None and 'synced' or 'never' for c in s.scalars(select(BankConnection))})))")"
  echo "connections: ${statuses:-none}"
  echo "$statuses" | grep -qw synced || fail c21 "no production connection has synced"
  railway logs --service api --environment "$PROD" --lines 5000 | grep 'POST /v1/webhooks/plaid' | grep -c '" 200' >/dev/null \
    || fail c21 "no 200 answer to a Plaid webhook in the production logs"
  echo "PASS c21"
}

c22() { evidence c22 C22; echo "PASS c22"; }

c23() {
  http_check c23 "https://$(domain_of api)/healthz/ready" 200 '{"status":"ok"}'
  local counts; counts="$(remote "$PROD" "$BUSINESS_COUNT")"
  echo "Restore drill A, B: $counts"
  [ "$counts" = "1 0" ] || fail c23 "expected A=1 B=0"
  echo "PASS c23"
}

c24() {
  local f=context/operations/production.md
  [ -f "$f" ] || fail c24 "$f does not exist"
  python3 - "$f" <<'EOF' || fail c24 "runbook sections incomplete"
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
def section(title):
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else None
restore, drill = section("Restore a backup"), section("Last drill")
assert restore and re.search(r"^1\. ", restore, re.M) and re.search(r"^2\. ", restore, re.M), "numbered steps"
assert drill and re.search(r"\b\d{4}-\d{2}-\d{2}\b", drill), "drill date"
assert re.search(r"[Bb]ackup[^\n]*\d{4}-\d{2}-\d{2}", drill), "backup timestamp"
assert re.search(r"\b\d+ minutes?\b", drill), "minutes"
EOF
  echo "PASS c24"
}

c25() {
  local counts; counts="$(remote "$PROD" "$BUSINESS_COUNT")"
  [ "$counts" = "0 0" ] || fail c25 "drill businesses remain: $counts"
  echo "PASS c25"
}

c30() { evidence c30 C30; echo "PASS c30"; }

c31() {
  local row
  for row in C31-api-issue C31-api-metric C31-web-issue C31-web-metric C31-railway-deploy; do
    evidence c31 "$row"
  done
  echo "PASS c31"
}

c32() {
  (cd services/core && uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q) >/dev/null \
    || fail c32 "api checks failed"
  echo "PASS c32"
}

[ $# -gt 0 ] || { echo "usage: $0 c1 [c2 ...]" >&2; exit 2; }
for check in "$@"; do "$check" || exit 1; done
