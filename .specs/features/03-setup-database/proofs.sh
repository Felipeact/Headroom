#!/usr/bin/env bash
# Proofs for spec 03 checks. Usage: bash .specs/features/03-setup-database/proofs.sh c5 [c6 ...]
# The other checks are pytest tests; these assert on tracked files, a live dev server across a
# Postgres stop, or the exit codes of the whole tool chain.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
PORT=8124

fail() { echo "FAIL $CHECK: $*" >&2; exit 1; }
in_core() { (cd "$CORE" && "$@"); }

c5() {
  local hits
  hits="$(git -C "$ROOT" grep -nIE '[a-z][a-z0-9+.-]*://[^/[:space:]:@]+:[^/[:space:]@]+@|localdev' \
    -- services/core ':(exclude)services/core/.env.example' || true)"
  [ -z "$hits" ] || { echo "$hits" >&2; fail "credentialed URL or password in tracked code"; }
}

c6() {
  git -C "$ROOT" ls-files --error-unmatch services/core/.env.example >/dev/null || fail ".env.example not tracked"
  tr -d '\r' < "$CORE/.env.example" \
    | grep -qx 'DATABASE_URL=postgresql+psycopg://headroom:localdev@localhost:5432/headroom' \
    || fail ".env.example does not set the compose DATABASE_URL"
  for want in 'POSTGRES_USER: headroom' 'POSTGRES_PASSWORD: localdev' 'POSTGRES_DB: headroom' '"5432:5432"'; do
    grep -qF "$want" "$ROOT/docker-compose.yml" || fail "docker-compose.yml no longer has $want"
  done
  git -C "$ROOT" check-ignore -q services/core/.env.local || fail ".env.local is not ignored"
}

wait_healthy() {
  local s=""
  for _ in $(seq 1 40); do
    s="$(docker inspect -f '{{.State.Health.Status}}' headroom-dev-postgres-1 2>/dev/null || true)"
    [ "$s" = healthy ] && return 0
    sleep 2
  done
  return 1
}

ready_status() {
  in_core uv run python -c '
import sys, urllib.error, urllib.request
try:
    print(urllib.request.urlopen("http://127.0.0.1:'"$PORT"'/healthz/ready", timeout=10).status)
except urllib.error.HTTPError as e:
    print(e.code)
'
}

c10() {
  local log pid ok=1 first second
  docker compose -f "$ROOT/docker-compose.yml" up -d postgres >/dev/null 2>&1
  wait_healthy || fail "compose Postgres never became healthy"
  log="$(mktemp)"
  (cd "$CORE" && exec uv run fastapi dev app/main.py --port "$PORT") >"$log" 2>&1 &
  pid=$!
  in_core uv run python -c '
import sys, time, urllib.request
for _ in range(60):
    try:
        urllib.request.urlopen("http://127.0.0.1:'"$PORT"'/healthz/live"); break
    except OSError:
        time.sleep(0.5)
else:
    sys.exit("dev server never answered")
' || true
  first="$(ready_status || echo none)"
  docker compose -f "$ROOT/docker-compose.yml" stop postgres >/dev/null 2>&1
  second="$(ready_status || echo none)"
  docker compose -f "$ROOT/docker-compose.yml" start postgres >/dev/null 2>&1
  wait_healthy || echo "warning: Postgres restarted but is not healthy yet" >&2
  [ "$first" = 200 ] && [ "$second" = 503 ] && ok=0
  if command -v taskkill >/dev/null 2>&1; then
    taskkill //F //T //PID "$(ps -p "$pid" -o winpid= 2>/dev/null || echo "$pid")" >/dev/null 2>&1 || true
  fi
  kill "$pid" 2>/dev/null || true
  [ "$ok" -eq 0 ] || { cat "$log" >&2; fail "ready was $first while running and $second after stop (want 200, 503)"; }
}

c14() {
  local env="$CORE/migrations/env.py"
  tr -d '\r' < "$env" | grep -qx 'from app.db import Base' || fail "env.py does not import Base from app.db"
  tr -d '\r' < "$env" | grep -qx 'target_metadata = Base.metadata' || fail "target_metadata is not Base.metadata"
}

c15() {
  in_core uv run ruff format --check . || fail "ruff format --check exited non-zero"
  in_core uv run ruff check . || fail "ruff check exited non-zero"
  in_core uv run mypy app || fail "mypy app exited non-zero"
  in_core uv run pytest -q || fail "pytest exited non-zero"
}

[ $# -gt 0 ] || { echo "usage: $0 c5 [c6 ...]" >&2; exit 2; }
for CHECK in "$@"; do
  "$CHECK"
  echo "PASS $CHECK"
done
