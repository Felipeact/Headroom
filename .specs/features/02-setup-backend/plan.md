# 02 - Backend scaffold

## Problem

The repository has no API. Spec 03 (database), spec 08 (errors and logging), spec 09 (typed client) and every backend module need a FastAPI project with a lockfile, a test runner and strict type checking to build on, and none of them can start until it exists. A Python project assembled from memory (hand-written `pyproject.toml`, hand-pinned versions, lockfile written by hand) is the failure the roadmap's set-up decision exists to prevent. Railway (spec 05) also has no endpoint to probe for liveness.

When this ships, `services/core/` installs with `uv sync`, serves `GET /healthz/live`, and passes ruff, ruff format, mypy strict and pytest. The source gives no evidence beyond the roadmap's build order.

## Flow

The project reuses `uv init` and `uv add` for every generated file. Only the app module, the test and the tool config are written by hand.

0. `uv init --app --no-package --python 3.12 services/core` (door 1, door 4): creates `pyproject.toml`, `.python-version`, `main.py` and `README.md`. It skips `git init` because the root is already a repository.
1. `uv add "fastapi[standard]" sqlalchemy "psycopg[binary]" alembic pydantic-settings` and `uv add --dev pytest ruff mypy` (door 2): writes the dependencies and `uv.lock`, and downloads managed CPython 3.12 into `.venv/`.
2. Hand edit: delete the generated `main.py`. Add `app/__init__.py` and `app/main.py`, a FastAPI app with `GET /healthz/live` (door 3).
3. Hand edit: add `tests/test_health.py` (TestClient), plus the `[tool.ruff]`, `[tool.mypy]` and `[tool.pytest.ini_options]` blocks in `pyproject.toml`.
4. Out: `uv run fastapi dev app/main.py` serves `/healthz/live` and `/docs` on `http://localhost:8000`.

## Impact

| Front | What changes |
| --- | --- |
| repository | new `services/core/`, matching the layout in root `AGENTS.md` |
| route convention | `/healthz/*` lives **outside** `/v1`, which is an explicit exception to AGENTS.md's "All routes live under `/v1`". Probes are infrastructure, not API. Spec 03 adds `/healthz/ready` the same way. |
| ignore rules | new `services/core/.gitignore` for `__pycache__/` (uv's `.venv`, ruff, mypy and pytest caches ignore themselves) |
| lockfile | new `services/core/uv.lock`, which AGENTS.md's "Shared files" lockfile rules now cover |
| stored data | nothing to migrate |

## Relations

None. There is no stored-data shape change.

## Surface

| Route | In | Out | Status |
| --- | --- | --- | --- |
| `GET /healthz/live` | nothing | `{"status": "ok"}` | `200` |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. Python version and project kind | `uv init --app --python 3.12` gives `.python-version` `3.12` and `requires-python = ">=3.12"`, an app with no build backend, run as `app.main` | 3.14 (the version installed locally): the spec says 3.12, and `services/forecast-service/Dockerfile` already uses `python:3.12-slim`. `--package`/`--lib`: a build backend the API never publishes |
| 2. Dependency set | exactly the five runtime and three dev packages from the spec, versions resolved by `uv add` and pinned in `uv.lock` | hand-pinned versions in `pyproject.toml`: AGENTS.md says "never hand-write lockfiles", and unverified pins are from-memory risk |
| 3. Liveness probe contract | `GET /healthz/live` returns `200` and `{"status": "ok"}`, outside `/v1`, with no auth | `/v1/health`: Railway (spec 05) and the later k8s manifests probe a stable unversioned path, and a probe must not depend on Clerk (spec 10) |
| 4. Unpackaged layout flag (found mid-build) | `uv init --app --no-package --python 3.12`: uv 0.12.17's `--app` alone generated `src/core/__init__.py`, `[build-system]` `uv_build` and `[project.scripts]`; `--no-package` yields the flat `main.py` and no build backend that door 1 describes | the packaged default: the spec's "replace the generated `main.py`" has no `main.py` to replace, and `app/` would sit beside an unused `src/core` package |

- Nothing else in this change is hard to reverse. The ruff and mypy config and the test layout can be refactored later.

## Criteria

### S1: The API runs and answers liveness (P1)

A developer can start the API and see it alive.

**Acceptance Criteria**

1. WHEN `GET /healthz/live` is requested THEN the API SHALL respond `200` with JSON body exactly `{"status": "ok"}`
2. WHILE `uv run fastapi dev app/main.py` runs in `services/core/`, WHEN `GET http://localhost:8000/openapi.json` is requested THEN the response SHALL list path `/healthz/live` with method `get`, which is what `/docs` renders
3. The API project SHALL have `services/core/app/main.py`, `services/core/uv.lock`, `.python-version` containing `3.12`, and no `services/core/main.py`

### S2: The checks pass under the configured rules (P1)

Every later spec's "Before you finish" checks run green from day one.

**Acceptance Criteria**

4. WHEN `uv run pytest` runs in `services/core/` THEN it SHALL exit 0 with at least 1 test passed, and `tests/test_health.py` SHALL use `fastapi.testclient.TestClient`
5. WHEN `uv run ruff check .` and `uv run ruff format --check .` run THEN both SHALL exit 0
6. WHEN `uv run mypy app` runs THEN it SHALL exit 0, with `pyproject.toml` `[tool.mypy]` `strict = true`
7. The `pyproject.toml` ruff config SHALL select the default rules plus `I` (import sorting), so that IF an unsorted import is added to `app/` THEN `uv run ruff check .` SHALL exit non-zero
8. IF a function in `app/` lacks a return type annotation THEN `uv run mypy app` SHALL exit non-zero

### S3: Generated files stay generated (P1)

The only hand-written files are the app, the test, the tool config and the ignore file.

**Acceptance Criteria**

9. The project `pyproject.toml` `[project] dependencies` SHALL name exactly `fastapi[standard]`, `sqlalchemy`, `psycopg[binary]`, `alembic` and `pydantic-settings`, and the dev group SHALL name exactly `pytest`, `ruff` and `mypy`, as written by `uv add`
10. WHEN `uv lock --check` runs THEN it SHALL exit 0, proving the lockfile matches `pyproject.toml`
11. WHEN all the S2 checks have run THEN `git status --porcelain services/core` SHALL list no `.venv`, `__pycache__`, `.ruff_cache`, `.mypy_cache` or `.pytest_cache` path

**Independent test:** in a fresh clone, run `cd services/core && uv sync && uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest`, then `uv run fastapi dev app/main.py` and open `/docs`.

## Out of scope

| Excluded | Why |
| --- | --- |
| Settings, `.env.example`, database engine, Alembic init, `/healthz/ready` | spec 03 |
| RFC 9457 error handlers, structured logger, Sentry | spec 08 |
| `/v1` router and `app.export_openapi` | spec 09 and the first module spec |
| CI workflow | spec 04 |
| Module folders under `app/modules/` | created by the specs that own each module |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Health response model | a Pydantic model with `status: Literal["ok"]` as `response_model` | AGENTS.md: "Pydantic models at API boundaries", and it makes the `/docs` schema typed | n |
| How tests import `app` | `[tool.pytest.ini_options] pythonpath = ["."]` | an `--app` project is not installed into the venv, so `app` is importable only from the project root | n |
| `__pycache__` ignore location | new `services/core/.gitignore` rather than editing the root one | keeps the change inside the spec's folder. uv does not write a `.gitignore` inside an existing repository | n |
| Generated `README.md` | kept as generated | not in scope to edit, and harmless | n |
| Commit split | commit 1: raw `uv init` + `uv add` output; commit 2: app, test, config, `.gitignore`, spec status | keeps the generated files reviewable on their own | n |

**Open questions:** none. All are resolved or logged above.

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| API `GET /healthz/live` | response shape | AC 1 |
| API `GET /healthz/live` | error shape and codes | n/a: a liveness handler has no failure branch, and RFC 9457 errors are spec 08 |
| API `GET /healthz/live` | who may call it | n/a: a public liveness probe with no customer data. Spec 10 must keep it exempt from Clerk |
| API `GET /healthz/live` | versioning, rate limit | n/a: deliberately unversioned (door 3), and there is no rate limiting in v1 |
| command `uv run fastapi dev` | output, flags, failure | existing: FastAPI CLI behaviour, unwrapped; AC 2 |
| commands `ruff` / `mypy` / `pytest` | exit codes | AC 4–8 |
| document `/docs` | structure | existing: generated by FastAPI from the route; AC 2 |

## Sources

- `context/specs/02-setup-backend.md`: the commands and the two Done-when items
- `AGENTS.md`: "Before you finish a task" checks, the "Generate, don't hand-write" rule and the lockfile rules

