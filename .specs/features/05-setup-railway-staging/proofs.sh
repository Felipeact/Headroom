#!/usr/bin/env bash
# Proofs for spec 05 (staging on Railway). Usage: bash proofs.sh c1 [c2 ...]
# Each function exits non-zero on failure and prints "PASS cN" on success.
# Reads Railway through the CLI with --environment staging; never prints variable values.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 1
HERE=".specs/features/05-setup-railway-staging"
ENV=staging
DB_TEMPLATE='postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}'
SUBJECT_N='build(deploy): stage on railway with infrastructure as code (spec 05)'
SUBJECT_W='docs(frontend): say where the web app deploys (spec 05)'
SUBJECT_A='docs(core): say where the api deploys (spec 05)'

fail() { echo "FAIL $1: $2" >&2; exit 1; }

# The IaC SDK checks the CLI version by running "$_ --version"; Git Bash sets $_ to a path
# Node cannot execute on Windows, so point it at the real binary when there is one.
railway_iac() {
  local exe
  exe="$(npm root -g 2>/dev/null)/@railway/cli/bin/railway.exe"
  if [ -f "$exe" ]; then env _="$exe" "$exe" "$@"; else railway "$@"; fi
}

# json CODE [ARGS...]: run CODE with the parsed stdin bound to d; ARGS land in sys.argv[1:].
# Windows Python prints \r\n, so strip \r before the output reaches shell variables.
json() { python3 -c "import json,sys; d=json.load(sys.stdin); $1" "${@:2}" | tr -d '\r'; }

domain_of() {
  railway domain list --service "$1" --environment "$ENV" --json | json "print(d['domains'][0]['domain'])"
}

env_config() { railway environment config --environment "$ENV" --json; }

service_id() {
  railway service list --environment "$ENV" --json | json "print(next(s['id'] for s in d if s['name']=='$1'))"
}

deployments() { railway deployment list --service "$1" --environment "$ENV" --limit 100 --json; }

latest_success_id() {
  deployments api | json "print(next((x['id'] for x in d if x['status']=='SUCCESS'), ''))"
}

sha_of() {
  local sha
  sha="$(git log origin/development --fixed-strings --grep="$1" --format=%H -n 1)"
  [ -n "$sha" ] || fail "${2:-sha}" "no commit on origin/development with subject: $1"
  echo "$sha"
}

# Railway records a commit whose files match no watch pattern as a SKIPPED deployment that never builds.
has_deployment_for() { # service sha -> yes (reached SUCCESS) / no (absent or only SKIPPED) / other
  deployments "$1" | json "
s={x['status'] for x in d if (x.get('meta') or {}).get('commitHash')=='$2'}
print('yes' if 'SUCCESS' in s else 'no' if s<={'SKIPPED'} else 'other:'+','.join(sorted(s)))"
}

ci_succeeded() { # sha -> exit 0 when the CI run for that commit concluded success
  [ "$(gh run list --commit "$1" --workflow CI --json conclusion --jq '.[0].conclusion')" = "success" ]
}

http_check() { # name url expected_status expected_body
  local out status body
  out="$(curl -sS --max-time 30 -w '\n%{http_code}' "$2")" || fail "$1" "request to $2 failed"
  status="${out##*$'\n'}"; body="${out%$'\n'*}"
  [ "$status" = "$3" ] || fail "$1" "$2 answered $status, expected $3"
  [ "$body" = "$4" ] || fail "$1" "$2 body was '$body', expected '$4'"
}

c1() { http_check c1 "https://$(domain_of api)/healthz/ready" 200 '{"status":"ok"}'; echo "PASS c1"; }

c2() { http_check c2 "https://$(domain_of api)/healthz/live" 200 '{"status":"ok"}'; echo "PASS c2"; }

c3() {
  local id
  id="$(latest_success_id)"; [ -n "$id" ] || fail c3 "no SUCCESS api deployment"
  railway logs "$id" --service api --environment "$ENV" --deployment --lines 1000 | grep -c 'Context impl PostgresqlImpl' >/dev/null \
    || fail c3 "deploy logs of $id do not show alembic running"
  # `alembic current` exits 0 even with no version table, so ask the schema directly.
  local has_table
  has_table="$(railway ssh --service api --environment "$ENV" -- python -c \
    "from sqlalchemy import inspect; from app.db import get_engine; print(inspect(get_engine()).has_table('alembic_version'))" 2>/dev/null | tr -d '\r' | tail -1)"
  [ "$has_table" = "True" ] || fail c3 "alembic_version is missing from the staging database (got '$has_table')"
  echo "PASS c3"
}

# Deploys a broken copy of HEAD with `railway up`; Railway must fail it and keep the old deployment.
inject_fault() { # name python-snippet-that-breaks-the-export
  local name="$1" before tmp after
  before="$(latest_success_id)"; [ -n "$before" ] || fail "$name" "no SUCCESS api deployment before injecting"
  tmp="$(mktemp -d)"
  git archive HEAD | tar -x -C "$tmp"
  (cd "$tmp" && python3 -c "$2") || fail "$name" "could not break the export"
  railway up "$tmp" --path-as-root --service api --environment "$ENV" --ci --message "spec 05 $name fault injection" 2>&1 | tail -5
  rm -rf "$tmp"
  deployments api | json "x=d[0]; assert x['id']!='$before' and x['status']=='FAILED', (x['id'], x['status'])" \
    || fail "$name" "the injected deployment did not end FAILED"
  after="$(latest_success_id)"
  [ "$before" = "$after" ] || fail "$name" "the latest SUCCESS deployment changed from $before to $after"
  c1 >/dev/null || fail "$name" "staging stopped answering after the fault"
  restore_latest_api
}

# `railway service redeploy` without --from-source rebuilds the newest deployment, which is now the
# broken upload; redeploy from the configured source so the newest deployment is a good one again.
restore_latest_api() {
  railway service redeploy --service api --environment "$ENV" --from-source --yes >/dev/null \
    || fail restore "could not redeploy api from source"
  local i status
  for i in $(seq 1 60); do
    status="$(deployments api | json "print(d[0]['status'])")"
    case "$status" in
      SUCCESS) return 0 ;;
      FAILED|CRASHED|REMOVED) fail restore "redeploy from source ended $status" ;;
    esac
    sleep 15
  done
  fail restore "redeploy from source did not finish within 15 minutes"
}

c4() {
  inject_fault c4 "p='services/core/migrations/env.py'; s=open(p).read(); open(p,'w').write('raise SystemExit(\"spec 05 c4 fault\")\n'+s)"
  echo "PASS c4"
}

c5() {
  inject_fault c5 "p='services/core/app/main.py'; s=open(p).read(); open(p,'w').write(s+'''

from fastapi import Response as _R
app.router.routes = [r for r in app.router.routes if getattr(r, \"path\", \"\") != \"/healthz/ready\"]
@app.get(\"/healthz/ready\")
def _spec05_c5_fault() -> _R:
    return _R(status_code=503)
''')"
  echo "PASS c5"
}

c6() {
  railway domain list --service Postgres --environment "$ENV" --json | json "assert d['domains']==[], d" \
    || fail c6 "Postgres has a public domain"
  railway tcp-proxy list --service Postgres --environment "$ENV" --json | json "assert d['proxies']==[], d" \
    || fail c6 "Postgres has a TCP proxy"
  echo "PASS c6"
}

c7() {
  local url body headers
  url="https://$(domain_of web)/"
  body="$(mktemp)"
  headers="$(curl -sS --max-time 30 -D - -o "$body" "$url")" || fail c7 "request to $url failed"
  echo "$headers" | head -1 | grep -q ' 200' || fail c7 "$url did not answer 200"
  echo "$headers" | grep -iq '^content-type: text/html' || fail c7 "$url is not text/html"
  grep -q '<html' "$body" || fail c7 "$url body has no <html"
  rm -f "$body"
  echo "PASS c7"
}

c8() { node "$HERE/web-check.mjs" "$(domain_of web)" || fail c8 "web check failed"; echo "PASS c8"; }

c9() {
  local sha; sha="$(sha_of "$SUBJECT_A" c9)" || exit 1
  ci_succeeded "$sha" || fail c9 "CI for commit A $sha has not succeeded"
  [ "$(has_deployment_for api "$sha")" = yes ] || fail c9 "no api deployment for commit A $sha"
  echo "PASS c9"
}

c10() {
  local sha; sha="$(sha_of "$SUBJECT_W" c10)" || exit 1
  ci_succeeded "$sha" || fail c10 "CI for commit W $sha has not succeeded"
  [ "$(has_deployment_for web "$sha")" = yes ] || fail c10 "no web deployment for commit W $sha"
  echo "PASS c10"
}

# Railway acts after CI, so a commit is only "not deployed" once 5 minutes have passed since its CI run ended.
settled_since_ci() { # sha name
  local done_at
  done_at="$(gh run list --commit "$1" --workflow CI --json updatedAt --jq '.[0].updatedAt')"
  [ -n "$done_at" ] || fail "$2" "no CI run for $1"
  python3 -c "import datetime as t,sys; d=t.datetime.fromisoformat('$done_at'.replace('Z','+00:00')); sys.exit(0 if t.datetime.now(t.timezone.utc)-d>=t.timedelta(minutes=5) else 1)" \
    || fail "$2" "less than 5 minutes since CI finished for $1; run again later"
}

c11() {
  local w n; w="$(sha_of "$SUBJECT_W" c11)" || exit 1; n="$(sha_of "$SUBJECT_N" c11)" || exit 1
  settled_since_ci "$n" c11; settled_since_ci "$w" c11
  [ "$(has_deployment_for api "$w")" = no ] || fail c11 "api deployed commit W $w"
  [ "$(has_deployment_for api "$n")" = no ] || fail c11 "api deployed commit N $n"
  echo "PASS c11"
}

c12() {
  local a n; a="$(sha_of "$SUBJECT_A" c12)" || exit 1; n="$(sha_of "$SUBJECT_N" c12)" || exit 1
  settled_since_ci "$n" c12; settled_since_ci "$a" c12
  [ "$(has_deployment_for web "$a")" = no ] || fail c12 "web deployed commit A $a"
  [ "$(has_deployment_for web "$n")" = no ] || fail c12 "web deployed commit N $n"
  echo "PASS c12"
}

c13() {
  local svc id sha
  git fetch -q origin development
  for svc in api web; do
    id="$(service_id "$svc")"
    env_config | json "assert d['services']['$id']['source']['branch']=='development'" \
      || fail c13 "$svc does not track development"
    for sha in $(deployments "$svc" | json "print('\n'.join(h for h in ((x.get('meta') or {}).get('commitHash') for x in d) if h))"); do
      git merge-base --is-ancestor "$sha" origin/development || fail c13 "$svc deployed $sha, which is not on development"
    done
  done
  echo "PASS c13"
}

c14() {
  local f=.railway/railway.ts
  [ "$(grep -c '://' "$f")" = 1 ] || fail c14 "$f has more than one line with ://"
  grep -F -q "\"$DB_TEMPLATE\"" "$f" || fail c14 "the :// line is not the door 3 template"
  grep -o '\${{[A-Za-z_]*\.' "$f" | grep -v -q '\${{Postgres\.' && fail c14 "a reference names something other than Postgres"
  grep -E -i -q 'token|secret|railway\.internal|\.up\.railway\.app' "$f" && fail c14 "$f matches a forbidden pattern"
  echo "PASS c14"
}

c15() {
  local found; found="$(git ls-files | grep -E '(^|/)\.env')"
  [ "$found" = "services/core/.env.example" ] || fail c15 "tracked env files: $found"
  echo "PASS c15"
}

c16() {
  local id; id="$(service_id api)"
  env_config | json "import sys; v=d['services']['$id']['variables']['DATABASE_URL']['value']; ok=v==sys.argv[1]; print('match' if ok else 'mismatch'); sys.exit(0 if ok else 1)" "$DB_TEMPLATE" \
    || fail c16 "api DATABASE_URL is not the door 3 template"
  echo "PASS c16"
}
c17() {
  railway service list --environment "$ENV" --json | json "
names={s['name']:[r['name'] for r in s.get('regions') or []] for s in d}
for n in ('Postgres','api','web'):
    assert names.get(n) and all(r.startswith('us-east') for r in names[n]), (n, names.get(n))" \
    || fail c17 "a service is not in us-east"
  echo "PASS c17"
}

c18() {
  railway status --json | json "
for e in d['environments']['edges']:
    n=e['node']
    if n['name']!='$ENV':
        assert n['serviceInstances']['edges']==[], n['name']" \
    || fail c18 "an environment other than staging has service instances"
  echo "PASS c18"
}

c19() {
  railway service list --environment "$ENV" --json | json "assert sorted(s['name'] for s in d)==['Postgres','api','web'], [s['name'] for s in d]" \
    || fail c19 "staging services are not exactly Postgres, api, web"
  local svc dir id
  for pair in api:/services/core web:/frontend; do
    svc="${pair%%:*}"; dir="${pair#*:}"; id="$(service_id "$svc")"
    env_config | json "s=d['services']['$id']['source']; assert (s.get('rootDirectory'),s.get('repo'),s.get('branch'),s.get('checkSuites'))==('$dir','Felipeact/Headroom','development',True), s" \
      || fail c19 "$svc source settings differ"
  done
  echo "PASS c19"
}

c20() {
  local api web; api="$(service_id api)"; web="$(service_id web)"
  env_config | json "
a=d['services']['$api']; w=d['services']['$web']
assert a['build'].get('builder')=='RAILPACK' and a['build'].get('watchPatterns')==['/services/core/**'], a['build']
assert a['deploy'].get('preDeployCommand')==['alembic upgrade head'], a['deploy'].get('preDeployCommand')
assert a['deploy'].get('startCommand')=='fastapi run app/main.py', a['deploy'].get('startCommand')
assert a['deploy'].get('healthcheckPath')=='/healthz/ready', a['deploy'].get('healthcheckPath')
assert w['build'].get('builder')=='RAILPACK' and w['build'].get('watchPatterns')==['/frontend/**'], w['build']
assert w['deploy'].get('healthcheckPath')=='/', w['deploy'].get('healthcheckPath')" \
    || fail c20 "live build or deploy settings differ"
  echo "PASS c20"
}

c21() {
  (cd services/core && uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q) >/dev/null \
    || fail c21 "api checks failed"
  (cd frontend && npm run lint && npm run typecheck && npm test && npm run build) >/dev/null \
    || fail c21 "web checks failed"
  echo "PASS c21"
}

c22() {
  railway_iac config plan --detailed-exit-code >/dev/null 2>&1 || fail c22 "staging differs from .railway/railway.ts (or plan failed)"
  json "assert d['dependencies']=={'railway':'3.12.0'}, d['dependencies']" < .railway/package.json \
    || fail c22 ".railway/package.json does not pin railway 3.12.0"
  echo "PASS c22"
}

[ $# -gt 0 ] || { echo "usage: $0 c1 [c2 ...]" >&2; exit 2; }
for check in "$@"; do "$check" || exit 1; done
