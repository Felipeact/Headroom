#!/usr/bin/env bash
# Proofs for spec 02 checks. Usage: bash .specs/features/02-setup-backend/proofs.sh c2 [c3 ...]
# C1 is a pytest test; the rest assert on files, tool exit codes or a live dev server.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
CORE="$ROOT/services/core"
PORT=8123

fail() { echo "FAIL $CHECK: $*" >&2; exit 1; }
in_core() { (cd "$CORE" && "$@"); }
py() { in_core uv run python -c "$@"; }

# Copies the tool config and app/ into a scratch dir so a deliberately bad file never touches the repo.
scratch_copy() {
  local dir
  dir="$(mktemp -d)"
  cp "$CORE/pyproject.toml" "$dir/"
  cp -r "$CORE/app" "$dir/app"
  echo "$dir"
}

c2() {
  local log pid ok=1
  log="$(mktemp)"
  (cd "$CORE" && exec uv run fastapi dev app/main.py --port "$PORT") >"$log" 2>&1 &
  pid=$!
  if py '
import json, sys, time, urllib.request
base = "http://127.0.0.1:'"$PORT"'"
for _ in range(60):
    try:
        spec = json.load(urllib.request.urlopen(base + "/openapi.json"))
        break
    except OSError:
        time.sleep(0.5)
else:
    sys.exit("dev server never answered")
if "get" not in spec["paths"].get("/healthz/live", {}):
    sys.exit("openapi.json has no GET /healthz/live")
if urllib.request.urlopen(base + "/docs").status != 200:
    sys.exit("/docs did not return 200")
'; then ok=0; fi
  if command -v taskkill >/dev/null 2>&1; then
    taskkill //F //T //PID "$(ps -p "$pid" -o winpid= 2>/dev/null || echo "$pid")" >/dev/null 2>&1 || true
  fi
  kill "$pid" 2>/dev/null || true
  [ "$ok" -eq 0 ] || { cat "$log" >&2; fail "dev server check failed"; }
}

c3() {
  [ -f "$CORE/app/main.py" ] || fail "app/main.py missing"
  [ -f "$CORE/uv.lock" ] || fail "uv.lock missing"
  [ ! -e "$CORE/main.py" ] || fail "generated main.py still present"
  [ "$(tr -d '\r\n' < "$CORE/.python-version")" = "3.12" ] || fail ".python-version is not 3.12"
  py '
import tomllib
p = tomllib.load(open("pyproject.toml", "rb"))
assert p["project"]["requires-python"] == ">=3.12", p["project"]["requires-python"]
' || fail "requires-python is not >=3.12"
}

c4() {
  grep -Eq '^from fastapi\.testclient import TestClient$' "$CORE/tests/test_health.py" \
    || fail "tests/test_health.py does not import fastapi.testclient.TestClient"
  local out
  out="$(in_core uv run pytest -q 2>&1)" || { echo "$out" >&2; fail "pytest exited non-zero"; }
  echo "$out" | grep -Eq '[1-9][0-9]* passed' || fail "no passing test reported"
}

c5() {
  in_core uv run ruff check . || fail "ruff check exited non-zero"
  in_core uv run ruff format --check . || fail "ruff format --check exited non-zero"
}

c6() {
  py '
import tomllib
p = tomllib.load(open("pyproject.toml", "rb"))
assert p["tool"]["mypy"]["strict"] is True
' || fail "tool.mypy.strict is not true"
  in_core uv run mypy app || fail "mypy app exited non-zero"
}

c7() {
  local dir out
  dir="$(scratch_copy)"
  printf 'import sys\nimport os\n\nprint(os, sys)\n' > "$dir/app/unsorted.py"
  if out="$(cd "$dir" && uv run --project "$CORE" ruff check . 2>&1)"; then
    rm -rf "$dir"; fail "ruff accepted unsorted imports"
  fi
  rm -rf "$dir"
  echo "$out" | grep -q 'I001' || { echo "$out" >&2; fail "failure was not rule I001"; }
}

c8() {
  local dir
  dir="$(scratch_copy)"
  printf 'def untyped(x: int):\n    return x\n' > "$dir/app/untyped.py"
  if (cd "$dir" && uv run --project "$CORE" mypy app); then
    rm -rf "$dir"; fail "mypy accepted a function with no return annotation"
  fi
  rm -rf "$dir"
}

c9() {
  py '
import re, tomllib
p = tomllib.load(open("pyproject.toml", "rb"))
name = lambda req: re.split(r"[<>=!~ ;]", req, maxsplit=1)[0]
deps = sorted(name(d) for d in p["project"]["dependencies"])
dev = sorted(name(d) for d in p["dependency-groups"]["dev"])
want = sorted(["fastapi[standard]", "sqlalchemy", "psycopg[binary]", "alembic", "pydantic-settings"])
assert deps == want, deps
assert dev == ["mypy", "pytest", "ruff"], dev
' || fail "dependency set differs from the spec"
}

c10() { in_core uv lock --check || fail "uv.lock is out of date"; }

c11() {
  CHECK=c4 c4 >/dev/null; CHECK=c5 c5 >/dev/null; CHECK=c6 c6 >/dev/null
  local leaked
  leaked="$(git -C "$ROOT" status --porcelain --untracked-files=all -- services/core \
    | grep -E '\.venv|__pycache__|\.ruff_cache|\.mypy_cache|\.pytest_cache' || true)"
  [ -z "$leaked" ] || { echo "$leaked" >&2; fail "tool artefacts visible to git"; }
}

[ $# -gt 0 ] || { echo "usage: $0 c2 [c3 ...]" >&2; exit 2; }
for CHECK in "$@"; do
  "$CHECK"
  echo "PASS $CHECK"
done
