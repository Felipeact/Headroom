#!/usr/bin/env bash
# Proofs for spec 04 checks. Usage: bash .specs/features/04-setup-tests-and-ci/proofs.sh c1 [c2 ...]
# C1-C6 run the frontend npm scripts. C7-C10 and C13 read the workflow file. C11, C12, C15 and
# C17 read GitHub's records of real runs, and C14 and C16 read repository settings, through gh.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
WEB="$ROOT/frontend"
WORKFLOW="$ROOT/.github/workflows/ci.yml"
REPO="Felipeact/Headroom"
PROOF_BRANCH="ci/spec-04-proof"

fail() { echo "FAIL $CHECK: $*" >&2; exit 1; }
in_web() { (cd "$WEB" && "$@"); }

# Evaluates a Python expression over the parsed workflow (bound to `w`); prints the result as JSON.
wf() {
  uv run --quiet --no-project --with pyyaml python - "$WORKFLOW" "$1" <<'PY'
import json, sys, yaml
w = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
# PyYAML reads the bare key `on` as the boolean True.
if True in w:
    w["on"] = w.pop(True)
print(json.dumps(eval(sys.argv[2])))
PY
}

run_steps() { wf "[s['run'].strip() for s in w['jobs']['$1']['steps'] if 'run' in s]"; }

c1() {
  local script
  script="$(in_web node -p "require('./package.json').scripts.typecheck")"
  [ "$script" = "next typegen && tsc --noEmit" ] || fail "typecheck script is '$script'"
  rm -rf "$WEB/.next" "$WEB/next-env.d.ts"
  in_web npm run typecheck || fail "npm run typecheck exited non-zero on a fresh tree"
}

c2() {
  local probe="$WEB/app/zz-type-error.tsx"
  trap 'rm -f "$probe"' RETURN
  printf 'export const n: number = "not a number";\n' > "$probe"
  local out
  if out="$(in_web npm run typecheck 2>&1)"; then fail "typecheck passed with a type error"; fi
  echo "$out"
  grep -q 'zz-type-error\.tsx' <<<"$out" || fail "typecheck failed, but not on zz-type-error.tsx"
}

c3() {
  local out
  out="$(cd "$WEB" && env -u CI timeout 120 npm test -- --reporter=verbose 2>&1)" || { echo "$out" >&2; fail "npm test failed or did not exit within 120 s"; }
  echo "$out"
  grep -qE '(✓|√).*app/page\.test\.tsx' <<<"$out" || fail "app/page.test.tsx did not report passing"
  grep -q "environment: 'jsdom'" "$WEB/vitest.config.mts" || fail "vitest.config.mts does not use jsdom"
  grep -q "@testing-library/react" "$WEB/app/page.test.tsx" || fail "page test does not use Testing Library"
  grep -qE "from ['\"](\./page|@/app/page)['\"]" "$WEB/app/page.test.tsx" || fail "page test does not render app/page.tsx"
}

c4() {
  local a="$WEB/e2e/zz-canary.test.ts" b="$WEB/e2e/zz-canary.spec.ts"
  trap 'rm -f "$a" "$b"' RETURN
  mkdir -p "$WEB/e2e"
  for f in "$a" "$b"; do
    printf 'import { test, expect } from "vitest";\ntest("canary", () => { expect(1).toBe(2); });\n' > "$f"
  done
  (cd "$WEB" && env -u CI timeout 120 npm test) || fail "npm test ran a file under e2e/"
}

c5() {
  local cfg="$WEB/playwright.config.ts" out
  grep -qE "testDir: ['\"]\./e2e['\"]" "$cfg" || fail "testDir is not ./e2e"
  grep -qE "^\s*webServer:" "$cfg" || fail "no webServer"
  grep -qE "url: ['\"]http://localhost:3000['\"]" "$cfg" || fail "webServer url is not http://localhost:3000"
  grep -rqE "goto\(['\"]/['\"]\)" "$WEB/e2e" || fail "no e2e test loads /"
  out="$(cd "$WEB" && npm run test:e2e -- --reporter=list 2>&1)" || { echo "$out" >&2; fail "npm run test:e2e exited non-zero"; }
  echo "$out"
  grep -qE '[1-9][0-9]* passed' <<<"$out" || fail "no passing e2e test"
}

c6() {
  in_web npm run lint || fail "npm run lint exited non-zero"
  in_web npm run build || fail "npm run build exited non-zero"
}

c7() {
  [ "$(wf "w['name']")" = '"CI"' ] || fail "workflow name is not CI"
  [ "$(wf "sorted(w['on']['pull_request']['branches'])")" = '["development", "main"]' ] || fail "pull_request branches"
  [ "$(wf "w['on']['push']['branches']")" = '["development"]' ] || fail "push branches"
  [ "$(wf "sorted(w['jobs'])")" = '["api", "web"]' ] || fail "jobs are not exactly api and web"
  [ "$(wf "[j for j in w['jobs'] if 'name' in w['jobs'][j]]")" = '[]' ] || fail "a job has a name override"
}

c8() {
  [ "$(wf "w['jobs']['web']['defaults']['run']['working-directory']")" = '"frontend"' ] || fail "web does not run in frontend"
  [ "$(run_steps web)" = '["npm ci", "npm run lint", "npm run typecheck", "npm test", "npm run build"]' ] \
    || fail "web run steps are $(run_steps web)"
}

c9() {
  [ "$(wf "w['jobs']['api']['defaults']['run']['working-directory']")" = '"services/core"' ] || fail "api does not run in services/core"
  [ "$(wf "any(s.get('uses', '').startswith('astral-sh/setup-uv@') for s in w['jobs']['api']['steps'])")" = true ] \
    || fail "no astral-sh/setup-uv step"
  [ "$(wf "[s['run'].strip() for s in w['jobs']['api']['steps'] if 'run' in s][-4:]")" \
    = '["uv run ruff format --check .", "uv run ruff check .", "uv run mypy app", "uv run pytest"]' ] \
    || fail "api run steps are $(run_steps api)"
}

green_pr_run() {
  gh run list -R "$REPO" --workflow CI --branch "$PROOF_BRANCH" --event pull_request --status success \
    --limit 1 --json databaseId --jq '.[0].databaseId // empty'
}

c10() {
  [ "$(wf "w['jobs']['api']['services']['postgres']['image']")" = '"postgres:17"' ] || fail "service image is not postgres:17"
  [ "$(wf "w['jobs']['api']['services']['postgres']['ports']")" = '["5432:5432"]' ] || fail "service port is not 5432:5432"
  wf "w['jobs']['api']['env']['DATABASE_URL']" | grep -qE '^"postgresql\+psycopg://[^@]+@localhost:5432/' \
    || fail "DATABASE_URL does not point at localhost:5432 with postgresql+psycopg"
  local run log
  run="$(green_pr_run)"; [ -n "$run" ] || fail "no green CI run on $PROOF_BRANCH"
  log="$(gh run view "$run" -R "$REPO" --log --job "$(job_id "$run" api)")"
  grep -qE '[0-9]+ passed' <<<"$log" || fail "api log has no pytest passed summary"
  if grep -qE '[0-9]+ skipped' <<<"$log"; then fail "pytest skipped tests in CI"; fi
}

job_id() { gh run view "$1" -R "$REPO" --json jobs --jq ".jobs[] | select(.name == \"$2\") | .databaseId"; }
job_conclusions() { gh run view "$1" -R "$REPO" --json jobs --jq '[.jobs[] | "\(.name)=\(.conclusion)"] | sort | join(" ")'; }

c11() {
  local run
  run="$(green_pr_run)"; [ -n "$run" ] || fail "no green pull_request CI run on $PROOF_BRANCH"
  [ "$(job_conclusions "$run")" = "api=success web=success" ] || fail "run $run jobs: $(job_conclusions "$run")"
}

c12() {
  local run head
  run="$(gh run list -R "$REPO" --workflow CI --branch "$PROOF_BRANCH" --event pull_request --limit 1 \
    --json databaseId --jq '.[0].databaseId')"
  [ "$(gh run view "$run" -R "$REPO" --json conclusion --jq .conclusion)" = failure ] || fail "latest run $run did not fail"
  head="$(gh run view "$run" -R "$REPO" --json headSha --jq .headSha)"
  gh api "repos/$REPO/commits/$head" --jq '.files[].filename' | grep -qE '^frontend/.*\.tsx$' \
    || fail "head commit $head changes no .tsx under frontend/"
  [ "$(gh run view "$run" -R "$REPO" --json jobs \
      --jq '.jobs[] | select(.name == "web") | .steps[] | select(.name | endswith("npm run typecheck")) | .conclusion')" = failure ] \
    || fail "web step 'npm run typecheck' did not fail in run $run"
}

c13() {
  if grep -n 'secrets\.' "$WORKFLOW"; then fail "workflow references secrets"; fi
  local pg="w['jobs']['api']['services']['postgres']['env']"
  [ "$(wf "[$pg['POSTGRES_USER'], $pg['POSTGRES_PASSWORD'], $pg['POSTGRES_DB']]")" = '["headroom", "localdev", "headroom"]' ] \
    || fail "CI Postgres credentials differ from docker-compose.yml"
  for want in 'POSTGRES_USER: headroom' 'POSTGRES_PASSWORD: localdev' 'POSTGRES_DB: headroom'; do
    grep -qF "$want" "$ROOT/docker-compose.yml" || fail "docker-compose.yml no longer has $want"
  done
}

c14() {
  local b
  for b in development main; do
    [ "$(gh api "repos/$REPO/branches/$b/protection" --jq '.required_status_checks.contexts | sort | join(" ")')" = "api web" ] \
      || fail "$b does not require exactly api and web"
    [ "$(gh api "repos/$REPO/branches/$b/protection" --jq '.enforce_admins.enabled')" = false ] \
      || fail "$b enforces protection for admins"
  done
}

c15() {
  local state
  state="$(gh pr view "$PROOF_BRANCH" -R "$REPO" --json state,baseRefName,mergeStateStatus \
    --jq '"\(.state) \(.baseRefName) \(.mergeStateStatus)"')"
  [ "$state" = "OPEN development BLOCKED" ] || fail "pull request is '$state'"
}

c16() {
  local status
  status="$(gh api -i "repos/$REPO/vulnerability-alerts" 2>&1 | head -1 | tr -d '\r')"
  grep -q ' 204' <<<"$status" || fail "vulnerability-alerts answered '$status'"
}

c17() {
  local sha run
  sha="$(git -C "$ROOT" rev-parse origin/development)"
  run="$(gh run list -R "$REPO" --workflow CI --branch development --event push --commit "$sha" --limit 1 \
    --json databaseId --jq '.[0].databaseId // empty')"
  [ -n "$run" ] || fail "no push CI run for $sha"
  [ "$(gh run view "$run" -R "$REPO" --json conclusion --jq .conclusion)" = success ] || fail "run $run did not succeed"
  [ "$(job_conclusions "$run")" = "api=success web=success" ] || fail "run $run jobs: $(job_conclusions "$run")"
}

[ $# -gt 0 ] || { echo "usage: $0 c1 [c2 ...]" >&2; exit 2; }
for CHECK in "$@"; do
  "$CHECK"
  echo "PASS $CHECK"
done
