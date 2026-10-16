# 03 - Local database and migrations

## Problem

The API cannot store or read anything. Every module spec from 11 onward owns tables, and none of them can start until the API has a database connection, a declarative `Base` for models and a migration chain. Railway (spec 05) can only check that the process is up (`/healthz/live`); it cannot tell whether the API can reach its database, so a deploy with a bad `DATABASE_URL` would look healthy. The spec also requires that no database URL or password lives in the code, which today is trivially true only because there is no database code at all.

When this ships, a developer runs `uv run alembic upgrade head` against the local Postgres, and `GET /healthz/ready` answers `200` when the database answers and `503` when it does not. The source gives no evidence beyond the roadmap's build order.

## Flow

This reuses the FastAPI app and `/healthz/*` convention from spec 02 and the shared `docker-compose.yml` Postgres; Alembic's generated `migrations/` and `alembic.ini` are kept, with only `env.py` edited.

1. `DATABASE_URL` (process env, else `services/core/.env.local`) -> `app/settings.py` (door 1) - validates the scheme, hands a `Settings` object on
2. `app/db.py` (door 3) - builds the SQLAlchemy engine and session factory from `Settings`, owns `Base` and its `MetaData` naming convention
3. `GET /healthz/ready` -> `app/main.py` (exists) (door 2) - runs `SELECT 1` on the engine and returns `200` or `503`
4. `uv run alembic upgrade head` -> `migrations/env.py` (door 4) - reads the URL from `Settings` and `target_metadata` from `Base.metadata`, applies revisions to the database named in `DATABASE_URL`

## Impact

| Front | What changes |
| --- | --- |
| configuration | new required env var `DATABASE_URL`. Without it, settings fail at first use (not at import), so `/healthz/live` and its test still work with no database configured |
| local setup | the setup block in root `AGENTS.md` already says `cp .env.example .env.local` and `uv run alembic upgrade head`; this spec makes both real. No edit to AGENTS.md needed |
| test suite | `uv run pytest` now needs the local Postgres running for the database-backed tests. Spec 04's CI must provide one |
| Railway (spec 05) | Railway's Postgres plugin exposes `postgresql://...`; spec 05 must set `DATABASE_URL` with the `postgresql+psycopg://` scheme, or the API refuses to start (AC 3) |
| route convention | `/healthz/ready` sits beside `/healthz/live`, outside `/v1`, as spec 02's plan already announced |
| stored data | nothing to migrate; no revision exists yet |

## Relations

None - no tables. `Base` is created with no models; the first table arrives with spec 11.

## Surface

| Route | In | Out | Status |
| --- | --- | --- | --- |
| `GET /healthz/ready` | nothing | `{"status": "ok"}` or `{"status": "unavailable"}` | `200`, `503` |

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. Settings contract | `class Settings(BaseSettings)` in `app/settings.py`, `model_config = SettingsConfigDict(env_file=".env.local")`, field `database_url: str` with **no default**; process env overrides the file; a cached `get_settings()` is the only way code reads it | a default URL in code: breaks the spec's "no URL or password in code". Module-level `settings = Settings()`: importing `app.main` would then fail anywhere `DATABASE_URL` is unset, including the existing liveness test |
| 2. Readiness probe contract | `GET /healthz/ready`, no auth, outside `/v1`: `200 {"status": "ok"}` when `SELECT 1` succeeds, `503 {"status": "unavailable"}` on any SQLAlchemy error, no error detail in the body | RFC 9457 `application/problem+json`: spec 08 owns the error format, and a probe body is read by Railway, not by a client. `500`: load balancers treat `503` as "not ready yet", which is the meaning here |
| 3. Constraint naming convention | `Base(DeclarativeBase)` with `metadata = MetaData(naming_convention={"ix": "ix_%(column_0_label)s", "uq": "uq_%(table_name)s_%(column_0_name)s", "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s", "pk": "pk_%(table_name)s"})`, the convention from the SQLAlchemy docs | no convention: Postgres then names constraints itself, autogenerate cannot drop or alter them by name, and adding a convention after spec 11 means renaming every existing constraint in a migration |
| 4. Migration URL source | `alembic.ini` keeps no `sqlalchemy.url` value; `migrations/env.py` reads `get_settings().database_url` for both online and offline mode | the URL in `alembic.ini`: a committed file holding a connection string. `config.set_main_option(...)`: passes the URL through configparser, which breaks on a `%` in a password |

- Doors 1, 2 and 3 reach past this feature and get rows in `.specs/STATE.md` `## Decisions`.
- The engine's pool options, the session factory and the probe's connect timeout are reversible and settled in the diff.

## Criteria

### S1: Settings come from the environment (P1)

The API reads its database location from the environment and nowhere else.

**Acceptance Criteria**

1. WHEN `DATABASE_URL` is set in the process environment THEN `get_settings().database_url` SHALL equal it, even when `.env.local` sets a different value
2. WHEN `DATABASE_URL` is absent from the environment and `.env.local` in the working directory sets it THEN `get_settings().database_url` SHALL equal the file's value
3. IF `DATABASE_URL` does not start with `postgresql+psycopg://` THEN `Settings()` SHALL raise a `pydantic.ValidationError`
4. IF `DATABASE_URL` is set nowhere THEN `Settings()` SHALL raise a `pydantic.ValidationError`
5. The tracked files under `services/core/` other than `.env.example` SHALL contain no database URL with credentials and no `localdev` password (repeatable `git grep`)
6. The file `services/core/.env.example` SHALL be tracked and set `DATABASE_URL` to the `docker-compose.yml` database with the `postgresql+psycopg://` scheme, and `git check-ignore services/core/.env.local` SHALL exit 0

### S2: The API reports database readiness (P1)

Railway and developers can tell whether the API reaches its database.

**Acceptance Criteria**

7. WHILE the database named in `DATABASE_URL` accepts connections, WHEN `GET /healthz/ready` is requested THEN the API SHALL respond `200` with JSON body exactly `{"status": "ok"}`
8. IF the database named in `DATABASE_URL` does not accept connections THEN `GET /healthz/ready` SHALL respond `503` with JSON body exactly `{"status": "unavailable"}`, within 5 seconds
9. IF `GET /healthz/ready` responds `503` THEN the body SHALL contain no host, user, password or exception text
10. WHILE `DATABASE_URL` is unset, `GET /healthz/live` SHALL still respond `200`

### S3: Migrations run from the settings URL (P1)

Every later spec adds tables through Alembic autogenerate.

**Acceptance Criteria**

11. WHEN `uv run alembic upgrade head` runs against a newly created, empty database THEN it SHALL exit 0, and `uv run alembic current` SHALL then exit 0
12. The file `migrations/env.py` SHALL set `target_metadata` to `app.db.Base.metadata`, and `Base.metadata.naming_convention` SHALL contain the five keys `ix`, `uq`, `ck`, `fk`, `pk` from door 3
13. WHEN `uv run alembic upgrade head` runs THEN the migration SHALL target the database named in `DATABASE_URL`, not any value in `alembic.ini`
14. WHEN `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy app` and `uv run pytest` run in `services/core/` with the local Postgres up THEN all four SHALL exit 0

**Independent test:** `docker compose up -d postgres`, then in `services/core/`: `cp .env.example .env.local && uv run alembic upgrade head && uv run pytest`; `curl -i localhost:8000/healthz/ready` gives `200` with the API running, then `docker compose stop postgres` and the same call gives `503`.

## Out of scope

| Excluded | Why |
| --- | --- |
| Any table, model or migration revision | the first module spec that owns data (spec 11) |
| RFC 9457 error handlers and the structured logger | spec 08 |
| CI Postgres service | spec 04 |
| Railway `DATABASE_URL` wiring | spec 05 |
| Plaid, Clerk, Fernet and other secrets in `Settings` | the specs that introduce each one |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Where Postgres runs for the proofs | Docker Desktop, via the existing `docker compose up -d postgres` | Docker Desktop 29.8.0 is now installed and the compose Postgres answers healthy on `localhost:5432` (checked 2026-10-01); AC 7, 11, 13, 14 are provable | y |
| How "Postgres is stopped" is tested | the test overrides the engine with one built from the settings URL with its port swapped for a closed local port; the manual `docker compose stop` run is the repeatable check beside it | stopping a container from inside pytest makes the suite order-dependent and slow; swapping the port avoids writing a URL literal in the tests |
| Empty-database test | the test creates a uniquely named database through the settings URL, runs `alembic upgrade head` as a subprocess with `DATABASE_URL` pointing at it, then drops it | proves "empty" literally instead of relying on the shared dev database being empty; the compose user is a superuser, so `CREATE DATABASE` is allowed |
| Probe connect timeout | `connect_timeout=2` passed to psycopg (changed from 3 during the build) | bounds AC 8 when the host does not answer at all, instead of hanging on TCP. psycopg 3.3 applies it per resolved address with a 2 s floor, and `localhost` resolves to `::1` and `127.0.0.1`, so 3 gave a 6.0 s 503 on Windows; 2 gives 4.0 s |
| Alembic template | `uv run alembic init migrations` (the `generic` template), exactly as the spec says | the `pyproject` template exists in newer Alembic but would diverge from the spec's command |
| Baseline revision | none; `alembic upgrade head` with no revisions | stays small; spec 11 creates the first revision |
| Commit split | commit 1: raw `alembic init` output; commit 2: settings, db, `env.py` edits, readiness route, tests, `.env.example`, spec status | keeps the generated files reviewable on their own, as in spec 02 |

**Open questions:** none - the Docker blocker was resolved before the build.

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| API `GET /healthz/ready` | response shape | AC 7, AC 8 |
| API `GET /healthz/ready` | error shape and codes | AC 8, AC 9; RFC 9457 deferred to spec 08 (door 2) |
| API `GET /healthz/ready` | who may call it | n/a: public probe returning no customer data; spec 10 must keep `/healthz/*` exempt from Clerk |
| API `GET /healthz/ready` | versioning, rate limit | n/a: deliberately unversioned (door 2), no rate limiting in v1 |
| command `alembic upgrade head` | output, flags, exit codes | existing: Alembic CLI behaviour, unwrapped; AC 11, AC 13 |
| command `alembic upgrade head` | failure halfway | n/a: no revisions exist; Alembic runs each Postgres revision in a transaction (transactional DDL) |
| document `.env.example` | structure and what the reader does next | AC 6; the next step is already in AGENTS.md Setup (`cp .env.example .env.local`) |

## Sources

- `context/specs/03-setup-database.md`: the steps and the three Done-when items
- `AGENTS.md`: Setup block, "Security and data handling" (no secrets in code), and the generated-file rules
