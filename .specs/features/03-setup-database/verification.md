# 03 - Local database and migrations verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 714b59b..8d37120 (spec 03 commits `d18b347` raw `alembic init`, `8d37120` the build)
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

Scope reviewed: `services/core`, `.specs/features/03-setup-database`, `context/specs/03-setup-database.md`,
`AGENTS.md` (Setup, Security and data handling). Baseline `git status --porcelain` was empty before the
run and empty after the proofs (this report is the only change). The compose Postgres
`headroom-dev-postgres-1` was `healthy` before the run and `healthy` again after C10's stop/start. Port
8124 had no LISTEN socket after C10 (one TIME_WAIT only).

## Binding sources

Step 1 runs only under `ui`; this feature is `light`, so it did not run. For context only: the three
Done-when items of `context/specs/03-setup-database.md` map to C12 (upgrade on empty database), C7/C8/C10
(200 running, 503 stopped) and C5 (no URL or password in code); no contradiction noticed.

## Checks

All proofs run at HEAD `8d37120`. Pytest proofs in one invocation from `services/core`:
`uv run pytest -v tests/test_settings.py tests/test_health.py tests/test_migrations.py tests/test_db.py -k "test_process_env_overrides_env_file or test_env_file_used_when_process_env_absent or test_rejects_non_psycopg_scheme or test_missing_database_url_raises or test_ready_returns_ok_when_database_answers or test_ready_returns_unavailable_when_database_refuses or test_unavailable_body_leaks_nothing or test_live_ok_without_database_url or test_upgrade_head_on_empty_database or test_upgrade_targets_database_url or test_alembic_ini_has_no_url or test_naming_convention_matches_door_3"`
-> 15 passed, 1 deselected (`test_live_returns_ok`, spec 02), each named test listed individually as
PASSED (C3 as four parametrized cases). Shell proofs:
`bash .specs/features/03-setup-database/proofs.sh c5 c6 c14 c10 c15` -> exit 0, printed `PASS c5`,
`PASS c6`, `PASS c14`, `PASS c10`, `PASS c15`. All named tests and proof functions were added in this
diff. "or-fail" below stands for the script's `<cmd> OR fail "..."` idiom (pipes omitted to keep the
table parseable).

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | process env beats `.env.local` | pytest `test_process_env_overrides_env_file` PASSED | `services/core/tests/test_settings.py:28` - `assert get_settings().database_url == ENV_URL` (file sets `FILE_URL` at line 25, env sets `ENV_URL` at line 26) | PASS |
| C2 | `.env.local` used when env absent | pytest `test_env_file_used_when_process_env_absent` PASSED | `services/core/tests/test_settings.py:34` - `assert get_settings().database_url == FILE_URL` | PASS |
| C3 | 4 non-psycopg schemes raise `ValidationError` | pytest `test_rejects_non_psycopg_scheme` 4 cases PASSED | `services/core/tests/test_settings.py:49` - `with pytest.raises(ValidationError): Settings()`; parametrize list lines 40-43 holds exactly the 4 credential-free URLs | PASS |
| C4 | no env, no file -> `ValidationError` | pytest `test_missing_database_url_raises` PASSED | `services/core/tests/test_settings.py:54` - `with pytest.raises(ValidationError): Settings()` (autouse fixture chdir to tmp and `delenv`, lines 15-16) | PASS |
| C5 | no credentialed URL or `localdev` in tracked `services/core` except `.env.example` | `proofs.sh c5` -> `PASS c5` | `.specs/features/03-setup-database/proofs.sh:15` - `git grep -nIE '[a-z][a-z0-9+.-]*://[^/[:space:]:@]+:[^/[:space:]@]+@` alternation `localdev'` excluding `.env.example`; `proofs.sh:17` - `[ -z "$hits" ]` or-fail | PASS |
| C6 | `.env.example` tracked, sets compose URL; `.env.local` ignored | `proofs.sh c6` -> `PASS c6` | `.specs/features/03-setup-database/proofs.sh:23` - `grep -qx 'DATABASE_URL=postgresql+psycopg://headroom:localdev@localhost:5432/headroom'`; `proofs.sh:21` - `git ls-files --error-unmatch`; `proofs.sh:28` - `git check-ignore -q services/core/.env.local` (rule `.gitignore:2` (repo root) - `.env*`) | PASS |
| C7 | DB up -> `200 {"status": "ok"}` | pytest `test_ready_returns_ok_when_database_answers` PASSED | `services/core/tests/test_health.py:58` - `assert response.status_code == 200`; `test_health.py:59` - `assert response.json() == {"status": "ok"}` | PASS |
| C8 | closed port -> `503 {"status": "unavailable"}` under 5 s | pytest `test_ready_returns_unavailable_when_database_refuses` PASSED | `services/core/tests/test_health.py:68` - `assert response.status_code == 503`; `test_health.py:69` - `assert response.json() == {"status": "unavailable"}`; `test_health.py:70` - `assert elapsed < 5` | PASS |
| C9 | 503 body carries no host, user, password, exception words | pytest `test_unavailable_body_leaks_nothing` PASSED | `services/core/tests/test_health.py:80-81` - `for secret in (url.host, url.username, url.password): assert secret; assert secret not in body`; `test_health.py:83` - `for word in ("Error", "Exception", "Traceback"): assert word not in body` | PASS |
| C10 | real dev server: 200 running, 503 after `docker compose stop`, Postgres restarted | `proofs.sh c10` -> `PASS c10`; container healthy afterwards | `.specs/features/03-setup-database/proofs.sh:73` - `[ "$first" = 200 ] && [ "$second" = 503 ] && ok=0`; `proofs.sh:78` - `[ "$ok" -eq 0 ]` or-fail; restart at `proofs.sh:71` - `docker compose ... start postgres` | PASS |
| C11 | `DATABASE_URL` unset -> `/healthz/live` 200 | pytest `test_live_ok_without_database_url` PASSED | `services/core/tests/test_health.py:52` - `assert response.status_code == 200` (after `chdir(tmp_path)` and `delenv("DATABASE_URL")`, lines 44-45) | PASS |
| C12 | fresh DB: upgrade 0, current 0, second upgrade 0 | pytest `test_upgrade_head_on_empty_database` PASSED | `services/core/tests/test_migrations.py:44` - `assert upgrade.returncode == 0`; `test_migrations.py:47` - `assert current.returncode == 0`; `test_migrations.py:50` - `assert again.returncode == 0` | PASS |
| C13 | migration lands in the `DATABASE_URL` DB; `alembic.ini` has no URL | pytest `test_upgrade_targets_database_url`, `test_alembic_ini_has_no_url` PASSED | `services/core/tests/test_migrations.py:62` - `assert "alembic_version" in tables` (inspected on the fresh DB); `test_migrations.py:69` - `assert ini.get("alembic", "sqlalchemy.url", fallback="").strip() == ""`; code `services/core/migrations/env.py:38` and `env.py:57` read `get_settings().database_url` | PASS |
| C14 | `env.py` uses `app.db.Base.metadata`; convention equals door 3 | `proofs.sh c14` -> `PASS c14`; pytest `test_naming_convention_matches_door_3` PASSED | `.specs/features/03-setup-database/proofs.sh:83` - `grep -qx 'from app.db import Base'`; `proofs.sh:84` - `grep -qx 'target_metadata = Base.metadata'`; `services/core/tests/test_db.py:15` - `assert {key: convention.get(key) for key in DOOR_3} == DOOR_3` (DOOR_3 literal near the top of the file matches plan door 3 key for key) | PASS |
| C15 | ruff format, ruff check, mypy, pytest all exit 0 | `proofs.sh c15` -> "10 files already formatted", "All checks passed!", "Success: no issues found in 4 source files", "16 passed", `PASS c15` | `.specs/features/03-setup-database/proofs.sh:88` - `ruff format --check .` or-fail; `proofs.sh:89` - `ruff check .` or-fail; `proofs.sh:90` - `mypy app` or-fail; `proofs.sh:91` - `pytest -q` or-fail | PASS |

### Level and sampling

- C7, C8, C9, C11 name a route and status and are proven through `TestClient` at the ASGI boundary;
  C10 crosses a real HTTP server and a real Postgres stop. No level gap.
- C12 and C13 run `uv run alembic` as a subprocess, the developer's command. No level gap.
- C3 claims four schemes and parametrizes exactly those four. No sampling gap.
- Startup-config row (two `DATABASE_URL` readers): read each assembly directly.
  API: `services/core/app/db.py:33` - `create_db_engine(get_settings().database_url)`.
  Alembic: `services/core/migrations/env.py:38` (offline) and `env.py:57` (online) - `get_settings().database_url`.
  `services/core/alembic.ini` contains no `url` line at all (grep for `url` returns nothing).
- Precision (minor, non-blocking): C10's claim includes "the proof restarts Postgres afterwards", but
  `proofs.sh:72` only warns if the restarted container is not healthy; it does not fail. Observed
  healthy after this run, so the claim holds at HEAD.
- Precision (minor, non-blocking): C8's under-5-seconds bound is proven against a refused local port
  only; the "host does not answer at all" path the connect timeout exists for (plan Assumptions) is not
  exercised. AC 8 says "does not accept connections", which the refused port satisfies.

### Disclosed changes judged

- C1-C3 sample URLs credential-free: claims in `checks.md` C1-C3 still state the same behaviour; C1/C2
  still use two distinct `postgresql+psycopg://` URLs and C3 still covers the same four schemes. C5's
  regex would flag a credentialed URL in the test files, so the change was required and harmless.
- Connect timeout 3 -> 2: `services/core/app/db.py:8` - `CONNECT_TIMEOUT_SECONDS = 2`, recorded in the
  plan Assumptions row (marked reversible in Landing). C8's `< 5` assertion passed.
- `plugins = ["pydantic.mypy"]` in `services/core/pyproject.toml` and `migrations/versions/.gitkeep`:
  both small, recorded under Handoff "Settled mid-build".

### Swept rows re-read

No Swept row resolves to "existing"; rows cite checks (C3, C4, C6, C8, C9, C10, C12) verified above or
are `n/a` (approved policy).

## Coverage

Coverage recompute does not run at `light`; the author's Coverage table was not re-derived.

## Test policy rows

Test policy verdicts do not run at `light` (and `checks.md` carries no Test policy section).

## Faults injected

Fault injection does not run at `light`.

## Gate

`uv run pytest -v ... -k "<12 named tests>"` - 15 passed, 0 failed;
`bash .specs/features/03-setup-database/proofs.sh c5 c6 c14 c10 c15` - 5 passed, 0 failed (exit 0;
c15's full suite 16 passed).

## Observations (non-blocking)

- pytest still emits `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated`
  (carried from spec 02).
