# 02 - Backend scaffold verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 6ae9f7d..e848843 (spec 02 commits `a27c4eb`, `e848843`; `9f8574b` is spec 01 and out of scope)
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

Scope reviewed: `services/core`, `.specs/features/02-setup-backend`, `context/specs/02-setup-backend.md`.
Baseline `git status --porcelain` was empty before the run and is identical after it (apart from this
report); port 8123 had no LISTEN socket after C2 (only a stale TIME_WAIT from a run before this
verification).

## Binding sources

Step 1 runs only under `ui`; this feature is `light`, so it did not run. For context only:
`context/specs/02-setup-backend.md` Steps still show `uv init --app --python 3.12` without
`--no-package`; the plan records the deviation as Landing door 4 (uv 0.12.17 defaults to a packaged
layout), so it is documented, not silent.

## Checks

All proofs run at HEAD `e848843`. C1: `cd services/core && uv run pytest tests/test_health.py -k test_live_returns_ok -v`
(`tests/test_health.py::test_live_returns_ok PASSED`, 1 passed). C2-C11: one invocation,
`bash .specs/features/02-setup-backend/proofs.sh c2 c3 c4 c5 c6 c7 c8 c9 c10 c11`, exit 0, each printed
`PASS cN` individually. Every named proof function exists in `proofs.sh` (c2 at line 22 through c11 at
line 120) and was added in this diff. In the evidence below, "or-fail" stands for the script's
`<cmd> OR fail "..."` shell idiom (pipe characters omitted to keep the table parseable).

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | `GET /healthz/live` -> `200`, body exactly `{"status": "ok"}` | pytest `-k test_live_returns_ok` exit 0, PASSED | `services/core/tests/test_health.py:11` - `assert response.status_code == 200`; `services/core/tests/test_health.py:12` - `assert response.json() == {"status": "ok"}` | PASS |
| C2 | dev server: `/openapi.json` lists GET `/healthz/live`, `/docs` 200 | `proofs.sh c2` -> `PASS c2` | `.specs/features/02-setup-backend/proofs.sh:38` - `if "get" not in spec["paths"].get("/healthz/live", {}): sys.exit(...)`; `proofs.sh:40` - `if urllib.request.urlopen(base + "/docs").status != 200: sys.exit(...)` | PASS |
| C3 | `app/main.py`, `uv.lock` exist; `.python-version` 3.12; `requires-python >=3.12`; no root `main.py` | `proofs.sh c3` -> `PASS c3` | `.specs/features/02-setup-backend/proofs.sh:53` - `[ ! -e "$CORE/main.py" ]`; `proofs.sh:54` - `[ "$(tr -d '\r\n' < "$CORE/.python-version")" = "3.12" ]`; `proofs.sh:58` - `assert p["project"]["requires-python"] == ">=3.12"` | PASS |
| C4 | `uv run pytest` exit 0 with >=1 passed; test imports `fastapi.testclient.TestClient` | `proofs.sh c4` -> `PASS c4` | `.specs/features/02-setup-backend/proofs.sh:63` - `grep -Eq '^from fastapi\.testclient import TestClient$'`; `proofs.sh:67` - `grep -Eq '[1-9][0-9]* passed'` | PASS |
| C5 | `ruff check .` and `ruff format --check .` exit 0 | `proofs.sh c5` -> "All checks passed!", "4 files already formatted", `PASS c5` | `.specs/features/02-setup-backend/proofs.sh:71` - `in_core uv run ruff check .` or-fail; `proofs.sh:72` - `in_core uv run ruff format --check .` or-fail | PASS |
| C6 | `mypy app` exit 0 and `tool.mypy.strict` true | `proofs.sh c6` -> "Success: no issues found in 2 source files", `PASS c6` | `.specs/features/02-setup-backend/proofs.sh:79` - `assert p["tool"]["mypy"]["strict"] is True`; config at `services/core/pyproject.toml:26` - `strict = true` | PASS |
| C7 | unsorted import in a copy of `app/` -> ruff non-zero with `I001` | `proofs.sh c7` -> `PASS c7` | `.specs/features/02-setup-backend/proofs.sh:88` - `if out="$(... ruff check . 2>&1)"; then ... fail`; `proofs.sh:92` - `grep -q 'I001'`; config `services/core/pyproject.toml:23` - `extend-select = ["I"]` (keeps defaults) | PASS |
| C8 | function without return annotation in a copy of `app/` -> mypy non-zero | `proofs.sh c8` -> mypy printed `app\untyped.py:1: error: Function is missing a return type annotation [no-untyped-def]`, `PASS c8` | `.specs/features/02-setup-backend/proofs.sh:99` - `if (cd "$dir" && uv run --project "$CORE" mypy app); then ... fail` | PASS |
| C9 | dependencies exactly the 5 runtime + 3 dev packages | `proofs.sh c9` -> `PASS c9` | `.specs/features/02-setup-backend/proofs.sh:113` - `assert deps == want, deps`; `proofs.sh:114` - `assert dev == ["mypy", "pytest", "ruff"], dev` | PASS |
| C10 | `uv lock --check` exit 0 | `proofs.sh c10` -> "Resolved 72 packages", `PASS c10` | `.specs/features/02-setup-backend/proofs.sh:118` - `in_core uv lock --check` or-fail `"uv.lock is out of date"` | PASS |
| C11 | after C4-C6, git sees no `.venv`/`__pycache__`/`.ruff_cache`/`.mypy_cache`/`.pytest_cache` | `proofs.sh c11` -> `PASS c11` | `.specs/features/02-setup-backend/proofs.sh:125` - `[ -z "$leaked" ]` or-fail `"tool artefacts visible to git"`; ignore rule `services/core/.gitignore:1` - `__pycache__/` | PASS |

### Level and sampling

- C1 crosses the ASGI boundary through `TestClient`; C2 crosses a real HTTP server. Both claims name a
  route/status and both are proven at that boundary: no level gap.
- C8 (precision, minor): the proof accepts any non-zero mypy exit, not specifically `no-untyped-def`.
  The run's own output shows the expected `[no-untyped-def]` error, so the claim holds at HEAD, but the
  proof would also pass on an unrelated mypy failure. Not a failed check; noted for hardening.
- C5 "default rules" is proven only by a clean `ruff check`; the config at `pyproject.toml:23` uses
  `extend-select`, which retains the defaults, so the claim is consistent with the code.
- No check claims more cases than its proof exercises.

### Swept rows re-read

- idempotency (C1): `services/core/app/main.py:13` - `@app.get("/healthz/live", ...)`; the handler returns
  a constant `LiveStatus(status="ok")` and touches no state. Holds.
- data lifecycle (C11): `services/core/.gitignore:1` ignores `__pycache__/`; uv/ruff/mypy/pytest caches
  self-ignore, confirmed by C11 passing with those directories present on disk. Holds.
- dependency failure (C10): `services/core/uv.lock` exists and `uv lock --check` passed. Holds.
- Remaining rows are `n/a` (approved policy); nothing to re-read.

## Coverage

Coverage recompute does not run at `light`; the author's Coverage table was not re-derived.

## Test policy rows

Test policy verdicts do not run at `light` (and `checks.md` carries no Test policy section).

## Faults injected

Fault injection does not run at `light`.

## Gate

`uv run pytest tests/test_health.py -k test_live_returns_ok -v` - 1 passed, 0 failed;
`bash .specs/features/02-setup-backend/proofs.sh c2 ... c11` - 10 passed, 0 failed (exit 0).

## Observations (non-blocking)

- pytest emits `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead`
  from `fastapi/testclient.py`. Harmless today; may need a dev dependency change later.
- The context spec's Steps block still shows the original `uv init` command without `--no-package`
  (see Binding sources note).
