#!/usr/bin/env bash
# Proofs for spec 09 that are commands rather than single tests. Usage: bash proofs.sh c4 [c5 ...]
# c9 and c11 run `npm run build` (a few minutes each). c16-c18 read GitHub Actions through
# `gh` and wait for the run to finish:
#   c16: C16_SHA = head of the scratch PR commit that changes an endpoint without regenerating
#   c17: C17_SHA = head of the scratch PR commit that regenerates openapi.json but not schema.d.ts
#   c18: C18_SHA = the feature commit pushed to development (default: origin/development)
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel)"
FE="$ROOT/frontend"
CORE="$ROOT/services/core"

fail() { echo "FAIL $1: $2" >&2; exit 1; }
pass() { echo "PASS $1"; }

c4() {
  (cd "$FE" && npm run api:types >/dev/null) || fail c4 "npm run api:types exited non-zero"
  grep -q '^export interface paths' "$FE/lib/api/schema.d.ts" || fail c4 "no 'export interface paths'"
  grep -q '"/healthz/live"' "$FE/lib/api/schema.d.ts" || fail c4 'no "/healthz/live" key'
  pass c4
}

c5() {
  (cd "$CORE" && uv run python -m app.export_openapi >/dev/null) || fail c5 "export exited non-zero"
  (cd "$FE" && npm run api:types >/dev/null) || fail c5 "api:types exited non-zero"
  local dirty
  dirty="$(cd "$ROOT" && git status --porcelain -- contracts/openapi.json frontend/lib/api/schema.d.ts)"
  [ -z "$dirty" ] || fail c5 "generated files differ from HEAD: $dirty"
  pass c5
}

c9() {
  local dir="$FE/app/dev/c9-scratch"
  mkdir -p "$dir"
  trap 'rm -rf "$dir"' RETURN
  cat >"$dir/leak.tsx" <<'EOF'
"use client"
import { api } from "@/lib/api/client"
export function Leak() {
  return <p>{typeof api}</p>
}
EOF
  cat >"$dir/page.tsx" <<'EOF'
import { Leak } from "./leak"
export default function Page() {
  return <Leak />
}
EOF
  local out
  if out="$(cd "$FE" && npm run build 2>&1)"; then fail c9 "build passed with a client import"; fi
  grep -q 'server-only' <<<"$out" || fail c9 "build failed, but not because of server-only"
  echo "$out" | grep -m1 'server-only'
  rm -rf "$dir"
  (cd "$FE" && npm run build >/dev/null 2>&1) || fail c9 "build fails even without the scratch files"
  pass c9
}

c10() {
  local f="$FE/lib/api/client.type-test.ts"
  grep -A1 '@ts-expect-error' "$f" | grep -q 'api.GET("/healthz/nope")' || fail c10 "no expect-error on the unknown path"
  grep -A1 '@ts-expect-error' "$f" | grep -q 'data.missing' || fail c10 "no expect-error on data.missing"
  (cd "$FE" && npm run typecheck >/dev/null 2>&1) || fail c10 "npm run typecheck failed"
  pass c10
}

c11() {
  (cd "$FE" && API_URL=http://api-sentinel.invalid:8000 npm run build >/dev/null 2>&1) || fail c11 "build failed"
  if grep -rlE 'API_URL|api-sentinel\.invalid' "$FE/.next/static" >/dev/null; then
    fail c11 "found in .next/static: $(grep -rlE 'API_URL|api-sentinel\.invalid' "$FE/.next/static" | head -3)"
  fi
  pass c11
}

c19() {
  grep -qx 'API_URL=http://localhost:8000' "$FE/.env.example" || fail c19 "line missing from .env.example"
  if (cd "$ROOT" && git ls-files -z frontend | xargs -0 grep -l 'NEXT_PUBLIC_API_URL' 2>/dev/null | grep -v '^$'); then
    fail c19 "NEXT_PUBLIC_API_URL appears in a tracked file"
  fi
  pass c19
}

# gh is not always on Git Bash's PATH on Windows.
command -v gh >/dev/null || PATH="$PATH:/c/Program Files/GitHub CLI"

# run_jobs SHA: prints the finished CI run's jobs as JSON, waiting up to 20 minutes.
run_jobs() {
  local sha="$1" id status
  for _ in $(seq 1 120); do
    id="$(gh run list --commit "$sha" --workflow CI --limit 1 --json databaseId --jq '.[0].databaseId' | tr -d '
')"
    if [ -n "$id" ]; then
      status="$(gh run view "$id" --json status --jq .status | tr -d '
')"
      [ "$status" = "completed" ] && { gh run view "$id" --json jobs; return 0; }
    fi
    sleep 10
  done
  return 1
}

# Reads the run_jobs JSON on stdin with Python, since jq is not installed everywhere.
jobs_py() { python3 -c "import json,sys; jobs=json.load(sys.stdin)['jobs']; $1" "${@:2}" | tr -d '
'; }
job_conclusion() { jobs_py "print(next(j['conclusion'] for j in jobs if j['name']==sys.argv[1]))" "$2" <<<"$1"; }
failed_step() { jobs_py "print(','.join(s['name'] for j in jobs if j['name']==sys.argv[1] for s in j['steps'] if s['conclusion']=='failure'))" "$2" <<<"$1"; }
job_names() { jobs_py "print(','.join(sorted(j['name'] for j in jobs)))" <<<"$1"; }

c16() {
  [ -n "${C16_SHA:-}" ] || fail c16 "C16_SHA is not set"
  local jobs; jobs="$(run_jobs "$C16_SHA")" || fail c16 "no finished CI run for $C16_SHA"
  [ "$(job_conclusion "$jobs" api)" = "failure" ] || fail c16 "api did not fail"
  [ "$(failed_step "$jobs" api)" = "Check the OpenAPI contract is current" ] \
    || fail c16 "api failed at '$(failed_step "$jobs" api)', not the drift step"
  pass c16
}

c17() {
  [ -n "${C17_SHA:-}" ] || fail c17 "C17_SHA is not set"
  local jobs; jobs="$(run_jobs "$C17_SHA")" || fail c17 "no finished CI run for $C17_SHA"
  [ "$(job_conclusion "$jobs" web)" = "failure" ] || fail c17 "web did not fail"
  [ "$(failed_step "$jobs" web)" = "Check generated API types are current" ] \
    || fail c17 "web failed at '$(failed_step "$jobs" web)', not the drift step"
  [ "$(job_conclusion "$jobs" api)" = "success" ] || fail c17 "api did not succeed"
  pass c17
}

c18() {
  local sha="${C18_SHA:-$(git rev-parse origin/development)}"
  local jobs; jobs="$(run_jobs "$sha")" || fail c18 "no finished CI run for $sha"
  [ "$(job_names "$jobs")" = "api,web" ] || fail c18 "job names are not exactly web and api"
  [ "$(job_conclusion "$jobs" web)" = "success" ] || fail c18 "web did not succeed"
  [ "$(job_conclusion "$jobs" api)" = "success" ] || fail c18 "api did not succeed"
  pass c18
}

[ $# -gt 0 ] || { echo "usage: bash proofs.sh c4 [c5 ...]" >&2; exit 2; }
for check in "$@"; do "$check"; done
