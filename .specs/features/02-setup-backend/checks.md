# 02 - Backend scaffold checks

Profile: light
Plan: `.specs/features/02-setup-backend/plan.md`

11 checks in 3 slices · 3 one-way doors · 0 open, of which 0 block

C1 is a pytest test. The other proofs are named functions in
`.specs/features/02-setup-backend/proofs.sh`, because they assert on files, tool exit codes or a
live dev server, which pytest inside the project cannot cleanly observe. Each function exits
non-zero on failure and prints `PASS cN` on success.

## Checks

### S1 - The API runs and answers liveness · 3 hand-written files · ~3k

**C1** - `GET /healthz/live` returns `200` with JSON body exactly `{"status": "ok"}` (AC 1, door 3)
Proof: `cd services/core && uv run pytest tests/test_health.py -k test_live_returns_ok`

**C2** - With `uv run fastapi dev app/main.py` running on port 8123, `GET /openapi.json` lists path `/healthz/live` with method `get`, and `GET /docs` returns `200` (AC 2)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c2`

**C3** - `services/core/app/main.py` and `services/core/uv.lock` exist, `services/core/.python-version` is `3.12`, `pyproject.toml` `requires-python` is `>=3.12`, and `services/core/main.py` does not exist (AC 3, door 1)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c3`

### S2 - The checks pass under the configured rules · config + 1 test · ~2k

**C4** - `uv run pytest` exits 0 with at least 1 passed, and `tests/test_health.py` imports `fastapi.testclient.TestClient` (AC 4)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c4`

**C5** - `uv run ruff check .` and `uv run ruff format --check .` both exit 0 (AC 5)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c5`

**C6** - `uv run mypy app` exits 0 and `pyproject.toml` `tool.mypy.strict` is `true` (AC 6)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c6`

**C7** - An unsorted-import file placed in a copy of `app/` makes `uv run ruff check` exit non-zero with rule `I001` (AC 7)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c7`

**C8** - A function with no return annotation placed in a copy of `app/` makes `uv run mypy` exit non-zero (AC 8)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c8`

### S3 - Generated files stay generated · generated only · ~1k

**C9** - `pyproject.toml` `project.dependencies` names exactly `fastapi[standard]`, `sqlalchemy`, `psycopg[binary]`, `alembic`, `pydantic-settings`, and `dependency-groups.dev` names exactly `pytest`, `ruff`, `mypy` (AC 9, door 2)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c9`

**C10** - `uv lock --check` exits 0 (AC 10, door 2)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c10`

**C11** - After C4-C6 run, `git status --porcelain --untracked-files=all services/core` lists no path containing `.venv`, `__pycache__`, `.ruff_cache`, `.mypy_cache` or `.pytest_cache` (AC 11)
Proof: `bash .specs/features/02-setup-backend/proofs.sh c11`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| Landing doors (3) | door 1 Python 3.12 app C3 · door 2 dependency set C9 · door 3 probe contract C1 | - |
| `GET /healthz/live` statuses (1) | 200 C1 | - |
| finish-checks from AGENTS.md (4) | `ruff format --check` C5 · `ruff check` C5 · `mypy app` C6 · `pytest` C4 | - |
| lint rules claimed (2) | default rules C5 · `I` import sorting C7 | - |
| runtime dependencies (5) | `fastapi[standard]` C9 · `sqlalchemy` C9 · `psycopg[binary]` C9 · `alembic` C9 · `pydantic-settings` C9 | - |
| dev dependencies (3) | `pytest` C9 · `ruff` C9 · `mypy` C9 | - |
| ignored artefacts (5) | `.venv` C11 · `__pycache__` C11 · `.ruff_cache` C11 · `.mypy_cache` C11 · `.pytest_cache` C11 | - |

- C1 and C2 name a status or route; C1 crosses the ASGI boundary through TestClient, C2 through a real HTTP server
- No other check claims more than the single case its proof exercises

## Swept

- validation: n/a - the only route takes no input
- failure modes: n/a - a liveness handler has no failure branch; error handling is spec 08
- idempotency: C1 - GET with no side effects; nothing is stored
- authorization: n/a - public liveness probe with no customer data (plan Observable); Clerk is spec 10
- concurrency: n/a - no shared state
- data lifecycle: C11 - local caches and the venv never enter git
- dependency failure: C10 - the lockfile pins every resolved version, so a registry change cannot alter the install
- state transitions: n/a - no state
- observability: n/a - structured logging and Sentry arrive in spec 08

## Handoff

- S1-S3 = ~6k (generated files are probed, not read; 5 small hand-written files plus proofs.sh), under the 150k budget - one builder

- **Boundary:** C1-C11 closed in the commit after `a27c4eb` (generator output)
- **Settled mid-build:** uv 0.12.17's `uv init --app` generated a packaged `src/core` layout; `--no-package` added to restore the flat layout door 1 describes (plan Landing row 4, Flow step 0)
- **Abandoned:** the first `uv init --app` output (packaged layout), deleted before any commit
