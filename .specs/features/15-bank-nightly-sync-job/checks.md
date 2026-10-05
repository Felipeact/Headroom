# 15 - Nightly sync job checks

Profile: light
Plan: `.specs/features/15-bank-nightly-sync-job/plan.md`

33 checks in 5 slices · 6 one-way doors · 1 open, which blocks go-live (the Railway apply, now authorized by the user)

Commands run from `services/core/` (`uv run pytest ...`). `bash .specs/features/15-bank-nightly-sync-job/proofs.sh <cNN>` runs from anywhere in the repo.

- **Isolated database:** `tests/test_nightly_sync.py` and `tests/test_run_due.py` run against a database of their own, created at Alembic head per test module. Their bank tables are emptied before each test, because `run_due` reads every connection in the database and the shared test database holds other tests' connections.
- **Plaid:** the tests use spec 14's `SyncFake`, extended so each connection has its own access token and so it can fail on demand. Sync calls are counted per access token. No test calls Plaid.
- **Clock:** a simulated clock is a plain `now` passed to `run_due(now)`.
- **Local times:** every "local" time in a claim is the business's IANA time zone applied to `now`.
- **"Synced":** a connection counts as synced when the fake received a `sync_transactions` call with that connection's token.

## Checks

### S1 - Every business's banks sync once a night, around 2 AM local time · 9 files · 75 KB · ~19k

**C1** - A connection created on 2026-10-05, whose business is in `America/Toronto`, with no nightly sync yet: `run_due(2026-10-20T06:00Z)` (02:00 local) syncs it once. The connection's `nightly_synced_on` is then `2026-10-20` (AC 1)
Proof: `uv run pytest tests/test_nightly_sync.py -k "due_connection_synced_once"`

**C2** - After C1's run, `run_due` at every hour from `2026-10-20T07:00Z` to `2026-10-21T05:00Z` (03:00 to 01:00 local) makes no sync call for that connection (AC 2)
Proof: `uv run pytest tests/test_nightly_sync.py -k "not_again_same_night"`

**C3** - Fall-back window. Each connection's `nightly_synced_on` is set to the night date of `2026-10-25T00:00Z` before the window starts. With `run_due` at minute 0 of every UTC hour from `2026-10-25T00:00Z` to `2026-11-07T23:00Z`:
- the `America/Vancouver` connection is synced exactly 14 times, at 02:00 local on each date from 2026-10-25 to 2026-11-07. British Columbia stays on UTC−7 from 2026-11-01 (tzdata 2026.4), so 02:00 local is 09:00 UTC on every one of those dates
- the `America/St_Johns` connection is synced exactly 14 times, at 02:30 local on the same 14 dates, across its 2026-11-01 fall-back

(AC 3)
Proof: `uv run pytest tests/test_nightly_sync.py -k "fall_back_window"`

**C4** - Spring-forward window, set up as C3 but over `2027-03-07T00:00Z` to `2027-03-20T23:00Z`:
- the `America/Vancouver` connection is synced exactly once for each local night date 2027-03-07 to 2027-03-20 (14 syncs), at 02:00 local every time, because British Columbia no longer changes clocks
- the `America/St_Johns` connection is synced 14 times: at 02:30 local, except 2027-03-14 at 03:30 NDT

(AC 4)
Proof: `uv run pytest tests/test_nightly_sync.py -k "spring_forward_window"`

**C5** - One connection per time zone in AD-029 (8: `America/St_Johns`, `America/Halifax`, `America/Toronto`, `America/Winnipeg`, `America/Regina`, `America/Edmonton`, `America/Vancouver`, `America/Whitehorse`), each with `nightly_synced_on` set to its night date of `2026-10-12T00:00Z`. Hourly `run_due` from `2026-10-12T00:00Z` to `2026-10-14T23:00Z` syncs each connection exactly 3 times, once on each local night date 2026-10-12, 2026-10-13 and 2026-10-14 (AC 5)
Proof: `uv run pytest tests/test_nightly_sync.py -k "every_time_zone"`

**C6** - A `America/Toronto` connection whose last finished night is 2026-10-19, with no run between 02:00 and 06:59 local on 2026-10-20: `run_due(2026-10-20T11:00Z)` (07:00 local) syncs it, and sets `nightly_synced_on` to `2026-10-20` (AC 6)
Proof: `uv run pytest tests/test_nightly_sync.py -k "catch_up_later_same_night"`

**C7** - A `America/Toronto` connection with `created_at` `2026-10-20T19:00Z` (15:00 local). Hourly `run_due` from `2026-10-20T20:00Z` to `2026-10-21T05:00Z` (16:00 to 01:00 local) makes no sync call. `run_due(2026-10-21T06:00Z)` (02:00 local) syncs it once (AC 7)
Proof: `uv run pytest tests/test_nightly_sync.py -k "created_tonight_waits"`

**C8** - Two businesses (`America/Toronto` and `America/Vancouver`), each with a due connection whose fake update adds one transaction. After one `run_due`, each business's stored transaction carries that business's `business_id`. Every row each sync wrote has the `business_id` of its own connection (AC 8)
Proof: `uv run pytest tests/test_nightly_sync.py -k "each_sync_scoped_to_its_business"`

**C9** - Only one function reads connections across businesses for the job: `bank_sync.repository.nightly_candidates`. Its single caller is in `bank_sync/service.py`, and no other repository function in `bank_sync` selects connections without a `business_id` filter, apart from spec 14's `connection_for_item` (AC 8)
Proof: `uv run pytest tests/test_nightly_sync.py -k "one_cross_business_read"`

### S2 - Overlapping runs never sync the same connection twice · 3 files · 50 KB · ~13k

**C10** - A due connection's row is held by another session's `SELECT ... FOR UPDATE`. Then `run_due`:
- returns within 5 seconds
- makes no sync call for it
- reports `skipped_locked` 1
- leaves its `nightly_synced_on` null

Once the other session commits, the next hourly `run_due` syncs it once (AC 9)
Proof: `uv run pytest tests/test_nightly_sync.py -k "locked_connection_skipped"`

**C11** - Two threads, each with its own session, call `run_due` at the same `now` over 2 due connections A and B. The fake holds the first sync call open until the second thread has started. Afterwards:
- each connection's token got exactly 1 sync call
- both connections' `nightly_synced_on` is the night date
- the two summaries' `synced` counts add up to 2

(AC 10)
Proof: `uv run pytest tests/test_nightly_sync.py -k "concurrent_runs_sync_once"`

**C12** - After one `run_due(now)` committed a connection's night, a second `run_due(now)` at the same `now` makes no sync call and reports `due` 0 (AC 11)
Proof: `uv run pytest tests/test_nightly_sync.py -k "second_run_sees_finished_night"`

**C13** - In a nightly sync that adds a transaction:
- while the fake holds the Plaid call open, another session's `SELECT ... FOR UPDATE NOWAIT` on the connection row fails with `LockNotAvailable`
- afterwards, the connection row and the new transaction row have the same Postgres `xmin`, so the outcome and the sync committed in one transaction

(AC 12)
Proof: `uv run pytest tests/test_nightly_sync.py -k "outcome_in_sync_transaction"`

### S3 - Failed syncs are retried, and repeated failures are flagged · 4 files · 55 KB · ~14k

**C14** - A `America/Toronto` connection whose fake sync always raises `PlaidError` (`ITEM_ERROR` / `ITEM_LOGIN_REQUIRED`), with a stored transaction and cursor `c0`.

After `run_due` at 02:00 local, `nightly_attempts` is `1` and `next_nightly_attempt_at` is 03:00 local. After the attempt at 03:00 they are `2` and 05:00, and after the attempt at 05:00 they are `3` and 09:00.

The stored transactions, balances and cursor are the same as before each attempt (AC 13)
Proof: `uv run pytest tests/test_nightly_sync.py -k "retry_delays_grow"`

**C15** - Same always-failing connection, with `run_due` every hour from 02:00 to 23:00 local on one night. Sync calls happen at exactly 02:00, 03:00, 05:00 and 09:00 local, 4 in total (AC 14)
Proof: `uv run pytest tests/test_nightly_sync.py -k "no_attempt_before_next_attempt_time"`

**C16** - After the 4th failed attempt (09:00 local), the connection holds:
- `nightly_synced_on` = that night's date
- `failed_nights` `1`
- `nightly_attempts` `0`
- `next_nightly_attempt_at` null

The next night's first attempt is at 02:00 local (AC 15)
Proof: `uv run pytest tests/test_nightly_sync.py -k "fourth_failure_ends_night"`

**C17** - An always-failing connection run hourly for 3 nights. `bank_sync.service.needs_attention(session, business_id=..., connection_id=...)` returns `False` after nights 1 and 2 (`failed_nights` 1 and 2), and `True` after night 3 (`failed_nights` 3) (AC 16)
Proof: `uv run pytest tests/test_nightly_sync.py -k "three_failed_nights_need_attention"`

**C18** - Clearing the flag, from a connection with `failed_nights` 3, one case per path:

| Path | Result |
| --- | --- |
| `bank_sync.service.sync_connection` succeeds (the webhook and connect path) | `failed_nights` `0`, and `needs_attention` returns `False` |
| a successful nightly sync | `failed_nights` `0`, and `needs_attention` returns `False` |
| `sync_connection` fails | `failed_nights` stays `3` |

(AC 17)
Proof: `uv run pytest tests/test_nightly_sync.py -k "success_clears_attention"`

**C19** - A connection whose first two nightly attempts fail and whose third (05:00 local) succeeds: after the third, `nightly_synced_on` is that night's date, `nightly_attempts` `0`, `next_nightly_attempt_at` null and `failed_nights` `0` (AC 18)
Proof: `uv run pytest tests/test_nightly_sync.py -k "success_after_retries_ends_night"`

**C20** - Three due connections in one run:

| Connection | Fake sync | Result |
| --- | --- | --- |
| P | raises `PlaidError` | `nightly_attempts` `1` |
| R | raises `RuntimeError("boom-secret")` | `nightly_attempts` `1` |
| S | succeeds | synced, `nightly_synced_on` set |

The summary reports `synced` 1 and `failed` 2, and no exception reaches the caller (AC 19)
Proof: `uv run pytest tests/test_nightly_sync.py -k "one_failure_does_not_stop_others"`

### S4 - The command does its work, reports it, and exits · 6 files · 40 KB · ~10k

**C21** - Exit code `0` when the run finishes:
- in-process, `run_due.main()` returns `0` with `get_plaid_client` patched to an always-failing fake and one due connection
- as a subprocess, `uv run python -m app.jobs.run_due` with `DATABASE_URL` set to the isolated database with no connections exits `0` within 60 seconds

(AC 20)
Proof: `uv run pytest tests/test_run_due.py -k "exit_zero"`

**C22** - Exit code `1` when the runner cannot start:
- `uv run python -m app.jobs.run_due` with `DATABASE_URL=postgresql+psycopg://headroom:pw-secret@127.0.0.1:1/none` exits `1`, and its stdout holds a JSON line with `event` `jobs.run_failed` and an `error_type`
- with `TOKEN_ENCRYPTION_KEYS=not-a-key` it also exits `1` with `jobs.run_failed`
- neither output contains `pw-secret` or `not-a-key`

(AC 21)
Proof: `uv run pytest tests/test_run_due.py -k "exit_one_when_runner_cannot_start"`

**C23** - With `JOBS` patched to `(raising_job, recording_job)`, where `raising_job` raises `ValueError`:
- `main()` returns `0`
- `recording_job` ran
- the logs hold `jobs.job_failed` with `job` `raising_job` and `error_type` `ValueError`

(AC 22)
Proof: `uv run pytest tests/test_run_due.py -k "failing_job_does_not_stop_others"`

**C24** - A run with one synced, one failed (`PlaidError` `ITEM_ERROR` / `ITEM_LOGIN_REQUIRED`, `request_id` `req-n1`) and one locked connection logs:
- exactly one `jobs.run_finished` line with `due` 3, `synced` 1, `failed` 1, `skipped_locked` 1
- one `bank_sync.sync_failed` line with that `connection_id`, `error_type` `ITEM_ERROR`, `error_code` `ITEM_LOGIN_REQUIRED` and `request_id` `req-n1`

(AC 23)
Proof: `uv run pytest tests/test_run_due.py -k "run_finished_counts"`

**C25** - In C24's run, plus a connection failing with `RuntimeError("boom-secret")` and a synced transaction named `Coffee secret-name`, the captured log output contains none of:
- the access tokens
- `boom-secret`
- `secret-name`

The `RuntimeError` failure is logged with `error_type` `RuntimeError` only (AC 24)
Proof: `uv run pytest tests/test_run_due.py -k "no_secrets_in_job_logs"`

**C26** - After `main()` returns, `app.db.get_engine().pool.checkedin()` is `0` (AC 25)
Proof: `uv run pytest tests/test_run_due.py -k "engine_disposed"`

**C27** - `main()`, with `SENTRY_DSN=https://public@o0.ingest.sentry.io/0` and `JOBS` patched to one job that records state when it runs:
- when that job runs, `sentry_sdk.get_client().is_active()` is `True` and `app.subscriptions.register` has run
- without `SENTRY_DSN`, `is_active()` is `False`

(AC 26)
Proof: `uv run pytest tests/test_run_due.py -k "main_sets_up_before_jobs"`

**C28** - Event delivery, with `app.subscriptions.SUBSCRIPTIONS` patched to `(("transactions.synced", recorder),)`:
- a nightly sync that adds a transaction, through `main()`, calls `recorder` once with the connection's `business_id`, and `recorder` can read the new transaction from a fresh session
- the API `lifespan` (entering `TestClient(app)`) registers the same recorder
- calling `register()` twice subscribes it once

(AC 27)
Proof: `uv run pytest tests/test_run_due.py -k "subscriptions_reach_job_events"`

### S5 - Railway runs the job every hour on staging · 3 files · 15 KB · ~4k

**C29** - In `.railway/railway.ts`, service `jobs` has:
- root `/services/core`, branch `development`, builder `RAILPACK`, watch pattern `/services/core/**`
- start `python -m app.jobs.run_due`, `cronSchedule` `0 * * * *`, `restartPolicyType` `NEVER`
- no `healthcheck` and no `preDeploy`
- `DATABASE_URL` = AD-006's template; every other variable a `${{api.<SAME NAME>}}` reference for `CLERK_JWT_KEY`, `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV`, `TOKEN_ENCRYPTION_KEYS`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT`
- membership in `project("headroom").resources`

(AC 28; the `DATABASE_URL` exception is door 7)
Proof: `bash .specs/features/15-bank-nightly-sync-job/proofs.sh c29`

**C30** - After `railway config apply`, `railway config plan --detailed-exit-code` exits `0` (AC 29)
Proof: `bash .specs/features/15-bank-nightly-sync-job/proofs.sh c30`

**C31** - The newest staging `jobs` deployment's log holds a line with `"event": "jobs.run_finished"` and no `jobs.run_failed` line, and that deployment's status is not `FAILED` or `CRASHED` (AC 30)
Proof: `bash .specs/features/15-bank-nightly-sync-job/proofs.sh c31`

### Doors and gates

**C32** - Migration (door 1). `alembic upgrade` from `de44856f468e` to head on a database holding one connection:
- adds `nightly_synced_on` (date, null), `nightly_attempts` (integer, not null, `0` for the existing row), `next_nightly_attempt_at` (timestamptz, null) and `failed_nights` (integer, not null, `0` for the existing row)
- an update setting `failed_nights = -1` fails with `ck_bank_connections_failed_nights`
- `alembic downgrade de44856f468e` removes the four columns and the constraint

(door 1)
Proof: `uv run pytest tests/test_migrations.py -k "nightly_state_upgrade_downgrade_and_check"`

**C33** - Every AGENTS.md API check passes: `ruff format --check`, `ruff check`, `mypy app`, the full `pytest`. `export_openapi` leaves `contracts/openapi.json` unchanged, because no route changed. The web checks are untouched, since `frontend/` does not change (all ACs)
Proof: `bash .specs/features/15-bank-nightly-sync-job/proofs.sh c33`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| one-way doors (7) | door 1 C32, C14-C19 · door 2 C1-C7 · door 3 C21, C23 · door 4 C10-C13 · door 5 C29-C31 · door 6 C27, C28 · door 7 (`jobs` `DATABASE_URL`) C29, C31 | - |
| entities (1) | `bank_connections` nightly state C32 | - |
| time zones in AD-029 (8) | C5, table-driven over all 8; St_Johns and Vancouver also C3, C4 | - |
| DST transitions (2; St. John's - British Columbia keeps UTC−7 from 2026-11-01) | fall back 2026-11-01 C3 · spring forward 2027-03-14 C4 | - |
| due-rule terms (4) | night date after created night C7 · night not finished C1, C2, C12 · retry time reached C15 · catch-up later in the night C6 | - |
| attempt outcomes per night (5) | 1st failure +1h C14 · 2nd +2h C14 · 3rd +4h C14 · 4th ends night C16 · success ends night C19 | - |
| `failed_nights` transitions (3) | +1 per failed night C16, C17 · reaches 3 -> needs attention C17 · reset by success C18 (both paths) | - |
| sync failure kinds (2) | `PlaidError` C14, C20 · any other exception C20 | - |
| lock holders a run meets (3) | another session's `FOR UPDATE` C10 · a concurrent job run C11 · after commit C12 | - |
| run counts in `jobs.run_finished` (4) | `due` C24 · `synced` C24 · `failed` C24 · `skipped_locked` C24 | - |
| exit codes (2) | `0` C21, C23 · `1` C22 (unreachable DB, invalid settings) | - |
| startup steps in `main()` (4) | logging C22 (JSON line before settings load) · Sentry C27 · `register()` C27 · engine disposed C26 | - |
| startup config: event subscriptions (2 assemblies) | API `lifespan` C28 · jobs `main()` C28 | - |
| startup config: settings in the new assembly (1; `api` is unchanged and proven by spec 05) | `jobs` service C29, C31 | - |

- C3 and C4 claim exact local times and counts over all 336 hourly runs of each window, so one test settles them. C5 is table-driven over all 8 zones.
- S1-S3 assert at the service layer through `run_due(now)`, the job's real entry point minus process start. S4 adds the process boundary (C21, C22 by subprocess). C31 is the only proof on staging.
- C13 and C11 run against Postgres with threads, because lock behaviour cannot be faked.
- No other check claims more than the single case its proof exercises.

## Swept

- validation: n/a - the command takes no input or flags (plan `Observable`); time zones come from AD-029's check constraint, and C5 covers all 8
- failure modes: C14, C16, C20 (a failed sync changes nothing but its attempt state), C22 (runner cannot start), C23 (one job raises)
- idempotency: C2, C12 (the same night twice), C28 (`register()` twice); the sync itself is spec 14's idempotent `sync_connection` (spec 14 C11)
- authorization: C8, C9 (each sync scoped to its connection's business; one cross-business read). No route, so no caller to authorize
- concurrency: C10, C11, C13 (row lock with `SKIP LOCKED`, outcome under the lock)
- data lifecycle: C32 (new columns, defaults for existing rows, no backfill); C7 (a new connection waits for its first night)
- dependency failure: C14-C16 (Plaid failing all night), C20 (non-Plaid error), C22 (database unreachable)
- state transitions: C14-C19 (attempts -> night finished -> failed nights -> needs attention -> cleared)
- observability: C24 (`jobs.run_finished` counts, `bank_sync.sync_failed`), C23 (`jobs.job_failed`), C22 (`jobs.run_failed`), C25 (nothing sensitive), C27 (Sentry in the job process)

## Handoff

- Existing files touched: `bank_sync/{service,repository,models}.py` (33 KB), `accounts/{service,repository}.py` (7 KB), `app/main.py` (3 KB), `tests/{conftest,test_migrations}.py` (25 KB), `test_transaction_sync.py` read for `SyncFake` (30 KB), `.railway/railway.ts` (3 KB), which is ~101 KB
- New files: `app/jobs/{__init__,run_due}.py`, `app/subscriptions.py`, the migration, `tests/test_nightly_sync.py`, `tests/test_run_due.py`, `proofs.sh`, which is ~60 KB
- Total: 161 KB / 4 = ~40k tokens, under the 150k budget - one builder

- **Settled mid-build:** C3 and C4's Vancouver claims were wrong. tzdata 2026.4 keeps British Columbia on UTC−7 from 2026-11-01, so Vancouver changes no clocks in either window. The user chose (2026-10-05) to keep Vancouver at 02:00 local every night, with St. John's covering both transitions. Only those expected values changed
- **Boundary:** C1-C30, C32, C33 closed at `ec66cf0`. Proofs green there: the API suite (365 passed), `proofs.sh c29`, `c30`, `c33`. C31 passed after the first scheduled staging run (2026-10-05T22:00:50Z, `due` 0, because every staging connection was created that day). Its proof now reads `railway logs --json`, since Railway shows JSON lines as `key=value`
- **Settled mid-build (builder decisions, none asked):**
  - The job module is `app/jobs/nightly.py`, because a submodule named `nightly_bank_sync` was shadowed by the function `app/jobs/__init__.py` imports.
  - The success outcome is written inside the sync's savepoint, so C13's same-`xmin` proof holds. Postgres gives a savepoint's writes its own transaction ID. This is still door 4: everything happens under the lock, with one commit.
  - Spec 14's migration test now targets its own revision `de44856f468e`, and its repository scope test also allows `nightly_candidates` (AC 8). No other assertion changed.
  - The user approved the push (2026-10-05). Railway skipped `api` for the push, because the head commit touched only `.railway/`, so `api` was redeployed from source; migrations `de44856f468e` and `c183e89c1a74` ran on staging.
  - `railway config apply` first planned to delete `api`'s hand-set Plaid and token-key variables, so they are now `preserve()`. A second apply was needed to set `jobs`' `checkSuites`.
- **Abandoned:** none
