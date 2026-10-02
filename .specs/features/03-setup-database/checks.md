# 03 - Local database and migrations checks

Profile: light
Plan: `.specs/features/03-setup-database/plan.md`

15 checks in 3 slices · 4 one-way doors · 0 open, of which 0 block

Pytest proofs run from `services/core/` with the compose Postgres up and `DATABASE_URL` reachable
(from `.env.local` or the process env). The other proofs are named functions in
`.specs/features/03-setup-database/proofs.sh`, because they assert on tracked files, a live dev
server across a Postgres stop, or the exit codes of the whole tool chain. Each function exits
non-zero on failure and prints `PASS cN` on success.

## Checks

### S1 - Settings come from the environment · 3 files · ~3k

**C1** - With `DATABASE_URL=postgresql+psycopg://env-host:5432/env_db` in the process env and `.env.local` in the working directory setting a different `postgresql+psycopg://` URL, `get_settings().database_url` equals the process-env value (AC 1, door 1)
Proof: `cd services/core && uv run pytest tests/test_settings.py -k test_process_env_overrides_env_file`

**C2** - With `DATABASE_URL` absent from the process env and `.env.local` in the working directory setting `DATABASE_URL=postgresql+psycopg://file-host:5432/file_db`, `get_settings().database_url` equals that value (AC 2, door 1)
Proof: `cd services/core && uv run pytest tests/test_settings.py -k test_env_file_used_when_process_env_absent`

**C3** - `Settings()` raises `pydantic.ValidationError` for each of the 4 URLs `postgresql://h/d`, `postgres://h/d`, `postgresql+psycopg2://h/d`, `sqlite:///headroom.db` (credential-free, so C5 holds over the test files too) (AC 3)
Proof: `cd services/core && uv run pytest tests/test_settings.py -k test_rejects_non_psycopg_scheme`

**C4** - With `DATABASE_URL` absent from the process env and no `.env.local` in the working directory, `Settings()` raises `pydantic.ValidationError` (AC 4, door 1)
Proof: `cd services/core && uv run pytest tests/test_settings.py -k test_missing_database_url_raises`

**C5** - `git grep` over tracked files under `services/core/`, excluding `.env.example`, finds no `<scheme>://<user>:<password>@` URL and no `localdev` (AC 5)
Proof: `bash .specs/features/03-setup-database/proofs.sh c5`

**C6** - `services/core/.env.example` is tracked and sets `DATABASE_URL=postgresql+psycopg://headroom:localdev@localhost:5432/headroom` (the `docker-compose.yml` user, password, port and database), and `git check-ignore services/core/.env.local` exits 0 (AC 6)
Proof: `bash .specs/features/03-setup-database/proofs.sh c6`

### S2 - The API reports database readiness · 3 files · ~3k

**C7** - With the database in `DATABASE_URL` accepting connections, `GET /healthz/ready` returns `200` with JSON body exactly `{"status": "ok"}` (AC 7, door 2)
Proof: `cd services/core && uv run pytest tests/test_health.py -k test_ready_returns_ok_when_database_answers`

**C8** - With the engine pointed at the settings URL with its port swapped to a closed local port, `GET /healthz/ready` returns `503` with JSON body exactly `{"status": "unavailable"}` in under 5 seconds (AC 8, door 2)
Proof: `cd services/core && uv run pytest tests/test_health.py -k test_ready_returns_unavailable_when_database_refuses`

**C9** - In that `503` response, the body text contains none of the settings URL's host, username or password, nor the words `Error`, `Exception` or `Traceback` (AC 9, door 2)
Proof: `cd services/core && uv run pytest tests/test_health.py -k test_unavailable_body_leaks_nothing`

**C10** - With `uv run fastapi dev app/main.py` on port 8124, `GET /healthz/ready` returns `200` while the compose Postgres runs, `503` after `docker compose stop postgres`, and the proof restarts Postgres afterwards (AC 7, AC 8; spec Done-when 2 literally)
Proof: `bash .specs/features/03-setup-database/proofs.sh c10`

**C11** - With `DATABASE_URL` absent from the process env and no `.env.local` in the working directory, `GET /healthz/live` returns `200` (AC 10, door 1)
Proof: `cd services/core && uv run pytest tests/test_health.py -k test_live_ok_without_database_url`

### S3 - Migrations run from the settings URL · generated + 3 files · ~4k

**C12** - On a newly created, uniquely named empty database, `uv run alembic upgrade head` exits 0, `uv run alembic current` then exits 0, and a second `uv run alembic upgrade head` also exits 0 (AC 11)
Proof: `cd services/core && uv run pytest tests/test_migrations.py -k test_upgrade_head_on_empty_database`

**C13** - After `uv run alembic upgrade head` with `DATABASE_URL` naming that fresh database, the table `alembic_version` exists in that database, and `alembic.ini` holds no non-empty `sqlalchemy.url` (AC 13, door 4)
Proof: `cd services/core && uv run pytest tests/test_migrations.py -k test_upgrade_targets_database_url`
Proof: `cd services/core && uv run pytest tests/test_migrations.py -k test_alembic_ini_has_no_url`

**C14** - `migrations/env.py` assigns `target_metadata = Base.metadata` with `Base` imported from `app.db`, and `Base.metadata.naming_convention` maps `ix`, `uq`, `ck`, `fk`, `pk` to exactly the five templates in door 3 (AC 12, door 3)
Proof: `bash .specs/features/03-setup-database/proofs.sh c14`
Proof: `cd services/core && uv run pytest tests/test_db.py -k test_naming_convention_matches_door_3`

**C15** - In `services/core/` with the compose Postgres up, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy app` and `uv run pytest` all exit 0 (AC 14)
Proof: `bash .specs/features/03-setup-database/proofs.sh c15`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| Landing doors (4) | door 1 settings contract C1 · door 2 probe contract C7 · door 3 naming convention C14 · door 4 migration URL source C13 | - |
| `GET /healthz/ready` statuses (2) | 200 C7 · 503 C8 | - |
| `DATABASE_URL` sources (3) | process env C1 · `.env.local` C2 · neither C4 | - |
| rejected schemes (4) | C3, table-driven over all 4 | - |
| naming convention keys (5) | `ix` C14 · `uq` C14 · `ck` C14 · `fk` C14 · `pk` C14 | - |
| 503 body must not carry (4) | host C9 · username C9 · password C9 · exception text C9 | - |
| finish-checks from AGENTS.md (4) | `ruff format --check` C15 · `ruff check` C15 · `mypy app` C15 · `pytest` C15 | - |
| startup config: `DATABASE_URL` reader (2 assemblies) | API app via `get_settings()` C7 · Alembic `env.py` via `get_settings()` C13 | - |

- C7, C8, C9, C11 cross the ASGI boundary through TestClient; C10 crosses a real HTTP server and a real Postgres stop
- C12 and C13 run Alembic as a subprocess, the same command a developer runs
- No other check claims more than the single case its proof exercises

## Swept

- validation: C3, C4 - wrong scheme and missing value both fail at `Settings()`
- failure modes: C8, C9 - an unreachable database gives a bounded, detail-free 503
- idempotency: C12 - a second `alembic upgrade head` exits 0; the probe's `SELECT 1` writes nothing
- authorization: n/a - public probe with no customer data (plan Observable); spec 10 keeps `/healthz/*` exempt from Clerk
- concurrency: n/a - no shared mutable state; pool options are reversible and settled in the diff
- data lifecycle: C12 - the migration test creates its own database and drops it; C6 - `.env.local` never enters git
- dependency failure: C8, C10 - refused connection and a stopped Postgres both give 503
- state transitions: n/a - no stateful entity
- observability: n/a - the structured logger arrives in spec 08

## Handoff

- S1-S3 = ~10k (about 8 small hand-written files plus proofs.sh; Alembic's generated files are read once, not iterated), under the 150k budget - one builder

- **Boundary:** C1-C15 closed in the commit after `d18b347` (raw `alembic init` output)
- **Settled mid-build:** C1-C3 sample URLs made credential-free (claims unchanged) because C5 forbids credentialed URLs in tracked files, tests included; probe `connect_timeout` lowered from 3 to 2 (plan Assumptions) because psycopg applies it per address and `localhost` has two; `plugins = ["pydantic.mypy"]` added so `Settings()` typechecks under strict mypy; empty `migrations/versions/.gitkeep` added so git keeps the folder Alembic reads
- **Abandoned:** none
