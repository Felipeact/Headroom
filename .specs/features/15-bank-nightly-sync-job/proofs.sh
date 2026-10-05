#!/usr/bin/env bash
# Proofs for spec 15 that are commands rather than single tests. Usage: bash proofs.sh c29 [c30 ...]
#   c29: the `jobs` service in .railway/railway.ts has the shape of doors 5 and 7
#   c30: staging matches .railway/railway.ts (`railway config plan --detailed-exit-code` exits 0)
#   c31: the newest staging `jobs` deployment logged `jobs.run_finished` and did not fail
#   c33: every AGENTS.md API check, and openapi.json unchanged by the export
# Reads Railway through the CLI with --environment staging; never prints variable values.
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
ENV=staging

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

# The IaC SDK checks the CLI version by running "$_ --version"; Git Bash sets $_ to a path
# Node cannot execute on Windows, so point it at the real binary when there is one (AD-007).
railway_iac() {
  local exe
  exe="$(npm root -g 2>/dev/null)/@railway/cli/bin/railway.exe"
  if [ -f "$exe" ]; then env _="$exe" "$exe" "$@"; else railway "$@"; fi
}

json() { python3 -c "import json,sys; d=json.load(sys.stdin); $1" "${@:2}" | tr -d '\r'; }

c29() {
  python3 - "$ROOT/.railway/railway.ts" <<'EOF' || fail c29 "the jobs service does not match doors 5 and 7"
import re, sys
src = open(sys.argv[1], encoding="utf-8").read()
start = src.index('const jobs = service("jobs", {')
end = src.index("\n  });", start)
block = src[start:end]
template = ("postgresql+psycopg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}"
            "@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}")
required = [
    'github(REPO, { branch: "development", rootDirectory: "/services/core", checkSuites: true })',
    'build: { builder: "RAILPACK", watchPatterns: ["/services/core/**"] }',
    'start: "python -m app.jobs.run_due"',
    'deploy: { cronSchedule: "0 * * * *", restartPolicyType: "NEVER" }',
    f'"{template}"',
]
missing = [r for r in required if r not in block]
assert not missing, missing
assert "healthcheck" not in block and "preDeploy" not in block, "healthcheck or preDeploy present"
env = dict(re.findall(r'^\s+([A-Z_]+): "([^"]*)"', block, re.M))
names = ["CLERK_JWT_KEY", "PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_ENV",
         "TOKEN_ENCRYPTION_KEYS", "SENTRY_DSN", "SENTRY_ENVIRONMENT"]
assert {n: env.get(n) for n in names} == {n: "${{api.%s}}" % n for n in names}, env
assert set(env) - {"start"} == set(names), sorted(env)
resources = re.search(r'project\("headroom", \{\s*resources: \[([^\]]*)\]', src).group(1)
assert "jobs" in [r.strip() for r in resources.split(",")], resources
EOF
  pass c29
}

c30() {
  (cd "$ROOT/.railway" && railway_iac config plan --detailed-exit-code >/dev/null 2>&1) \
    || fail c30 "staging differs from .railway/railway.ts (or plan failed)"
  pass c30
}

c31() {
  local id status
  id="$(railway deployment list --service jobs --environment "$ENV" --limit 20 --json \
    | json "print(d[0]['id'] if d else '')")"
  [ -n "$id" ] || fail c31 "no jobs deployment on staging"
  status="$(railway deployment list --service jobs --environment "$ENV" --limit 20 --json \
    | json "print(d[0]['status'])")"
  case "$status" in FAILED|CRASHED) fail c31 "newest jobs deployment is $status" ;; esac
  logs="$(railway logs "$id" --service jobs --environment "$ENV" --deployment --lines 500)"
  grep -q '"event": "jobs.run_finished"' <<<"$logs" || fail c31 "no jobs.run_finished line"
  if grep -q 'jobs.run_failed' <<<"$logs"; then fail c31 "a jobs.run_failed line"; fi
  pass c31
}

c33() {
  (cd "$CORE" && uv run ruff format --check . && uv run ruff check . && uv run mypy app \
    && uv run pytest -q -p no:logging) || fail c33 "an API check failed"
  (cd "$CORE" && uv run python -m app.export_openapi) || fail c33 "export failed"
  git -C "$ROOT" diff --exit-code -- contracts/openapi.json \
    || fail c33 "contracts/openapi.json changed"
  pass c33
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c29|c30|c31|c33 ..." >&2; exit 2; }
for check in "$@"; do
  case "$check" in
    c29) c29 ;;
    c30) c30 ;;
    c31) c31 ;;
    c33) c33 ;;
    *) echo "unknown check: $check" >&2; exit 2 ;;
  esac
done
