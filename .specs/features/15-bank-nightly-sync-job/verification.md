# 15 - Nightly sync job verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 625ae6a..8071204
**Round**: 2 - full (round 1 could not run the database proofs)
**Verifier**: independent sub-agent (author != verifier)

All 33 proofs were run at HEAD `8071204` on 2026-10-05, against the local Postgres on port 5432. Before the run, `get_engine().connect()` returned `select 1` = `1`. All 33 passed, and each has a located assertion that targets the values the check names. One gap must be fixed soon, though it does not block today. Many of these tests depend on the wall clock (finding 1 below). That is why the verdict is PASS with findings, not a clean PASS.

## Binding sources

Not run under `light`; step 1 runs only under `ui`. This spec has no screen and no route (plan `Surface`: none). The two "Done when" items in `context/specs/15-bank-nightly-sync-job.md` were read:
- Pacific and Newfoundland each sync once a night on a simulated clock: C3, C4
- overlapping runs never sync twice: C10-C12

## Checks

Pytest proofs ran in one invocation from `services/core`: `uv run pytest tests/test_nightly_sync.py tests/test_run_due.py tests/test_migrations.py -p no:logging -v -k "<the 29 selectors joined with or>"`. It exited `0`, with **31 passed, 9 deselected** in 23.30 s. C18's test is parametrized 3 ways, which gives 29 selectors and 31 tests. Each test is listed individually as PASSED.

Command proofs ran from the repo root: `bash .specs/features/15-bank-nightly-sync-job/proofs.sh c29 c30 c31 c33`.

Each selector matches exactly one test that this diff added. `rg -n "^def test_"` finds them at the `def` lines cited below. `git diff --stat 625ae6a..8071204` shows `test_nightly_sync.py` (+619) and `test_run_due.py` (+354) as new files, and `test_nightly_state_upgrade_downgrade_and_check` as a `+def` in `test_migrations.py`.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | Toronto connection synced once at 2026-10-20T06:00Z, `nightly_synced_on` 2026-10-20 | `-k due_connection_synced_once`: PASSED | `tests/test_nightly_sync.py:236` def; `:241` `assert fake.times(c.token) == [utc(2026, 10, 20, 6)]`; `:242` `assert state(c)["nightly_synced_on"] == date(2026, 10, 20)` | PASS |
| C2 | no sync 07:00Z-05:00Z after C1 | `-k not_again_same_night`: PASSED | `tests/test_nightly_sync.py:245` def; `:249` `hourly(utc(2026, 10, 20, 7), utc(2026, 10, 21, 5))` (inclusive, `:190-195`); `:252` `assert fake.times(c.token) == [utc(2026, 10, 20, 6)]` | PASS |
| C3 | fall-back window: 14 syncs each, Vancouver 02:00 (09:00Z), St_Johns 02:30 | `-k fall_back_window`: PASSED | `tests/test_nightly_sync.py:255` def; `:264-266` `local_times(fake, vancouver) == [local(VANCOUVER, ..., 2, 0) for d in days]`; `:267-269` St_Johns `..., 2, 30`; `:263` `days` = 14 dates from 2026-10-25; `:271` `== [9] * 14` | PASS |
| C4 | spring-forward window: 14 each; St_Johns 03:30 on 2027-03-14, otherwise 02:30; Vancouver 02:00 | `-k spring_forward_window`: PASSED | `tests/test_nightly_sync.py:274` def; `:284-286` Vancouver `local(VANCOUVER, ..., 2, 0)`; `:287-290` `local(ST_JOHNS, ..., 3 if d == spring else 2, 30)` | PASS |
| C5 | all 8 AD-029 zones, synced once each night 2026-10-12, 13, 14 | `-k every_time_zone`: PASSED | `tests/test_nightly_sync.py:293` def; `:41-50` `ALL_ZONES` (8); `:302` `assert nights == [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)]` | PASS |
| C6 | catch-up at 07:00 local (11:00Z), `nightly_synced_on` 2026-10-20 | `-k catch_up_later_same_night`: PASSED | `tests/test_nightly_sync.py:307` def; `:312` `== [utc(2026, 10, 20, 11)]`; `:313` `== date(2026, 10, 20)` | PASS |
| C7 | created 15:00 local waits until 02:00 | `-k created_tonight_waits`: PASSED | `tests/test_nightly_sync.py:316` def; `:321` `assert fake.times(c.token) == []`; `:324` `== [utc(2026, 10, 21, 6)]` | PASS |
| C8 | each sync's rows carry their own business's `business_id` | `-k each_sync_scoped_to_its_business`: PASSED | `tests/test_nightly_sync.py:327` def; `:341` `assert len(stored) == 2`; `:343-346` `any(business == c.business_id and pid.startswith(...))` per connection | PASS |
| C9 | one cross-business read, single caller in `service.py` | `-k one_cross_business_read`: PASSED | `tests/test_nightly_sync.py:349` def; `:359` `assert unscoped == ["connection_for_item", "nightly_candidates"]`; `:367` `== ["modules/bank_sync/service.py"]` | PASS |
| C10 | locked connection skipped in under 5 s, `skipped_locked` 1, null `nightly_synced_on`, synced at the next run | `-k locked_connection_skipped`: PASSED | `tests/test_nightly_sync.py:374` def; `:386` `< 5`; `:387` `== []`; `:388` `counts["skipped_locked"] == 1`; `:389` `is None`; `:395` `== [utc(2026, 10, 20, 7)]` | PASS |
| C11 | concurrent runs: 1 call per connection, both nights set, `synced` sum 2 | `-k concurrent_runs_sync_once`: PASSED | `tests/test_nightly_sync.py:398` def; `:415` `fake.entered.wait(10)` before the 2nd thread starts; `:423-424` `len(...) == 1`; `:425-426` `== date(2026, 10, 20)`; `:427` `sum(s["synced"] for s in summaries) == 2` | PASS |
| C12 | a second run at the same `now`: no call, `due` 0 | `-k second_run_sees_finished_night`: PASSED | `tests/test_nightly_sync.py:430` def; `:437` `== [now]`; `:438` `counts["due"] == 0` | PASS |
| C13 | NOWAIT fails during the sync; same `xmin` | `-k outcome_in_sync_transaction`: PASSED | `tests/test_nightly_sync.py:441` def; `:458` `isinstance(excinfo.value.orig, LockNotAvailable)`; `:474` `connection_xmin == transaction_xmin` | PASS |
| C14 | attempts 1/2/3, next attempt 03:00/05:00/09:00 local, data unchanged | `-k retry_delays_grow`: PASSED | `tests/test_nightly_sync.py:495` def; `:499-503` expected table; `:507` `nightly_attempts == attempts`; `:508` `next_nightly_attempt_at == next_at`; `:509` `snapshot(c.business_id) == before` | PASS |
| C15 | calls at exactly 02, 03, 05, 09 local | `-k no_attempt_before_next_attempt_time`: PASSED | `tests/test_nightly_sync.py:512` def; `:520-522` `local_times(fake, c) == [local(TORONTO, 2026, 10, 20, h) for h in (2, 3, 5, 9)]` | PASS |
| C16 | 4th failure ends the night; next night starts at 02:00 | `-k fourth_failure_ends_night`: PASSED | `tests/test_nightly_sync.py:525` def; `:530-535` `state(c) == {"nightly_synced_on": date(2026, 10, 20), "nightly_attempts": 0, "next_nightly_attempt_at": None, "failed_nights": 1}`; `:541` `[4:] == [local(TORONTO, 2026, 10, 21, 2)]` | PASS |
| C17 | `needs_attention` F, F, T at `failed_nights` 1, 2, 3 | `-k three_failed_nights_need_attention`: PASSED | `tests/test_nightly_sync.py:544` def; `:554` `assert seen == [(1, False), (2, False), (3, True)]` | PASS |
| C18 | success on either path clears; a failure keeps 3 | `-k success_clears_attention`: 3 params PASSED | `tests/test_nightly_sync.py:557-560` parametrize `["sync_connection", "nightly", "sync_connection_fails"]`; `:582` `failed_nights == 3`; `:585` `== 0`; `:586` `needs_attention(c) is False` | PASS |
| C19 | success at 05:00 after 2 failures ends the night | `-k success_after_retries_ends_night`: PASSED | `tests/test_nightly_sync.py:589` def; `:596` `len(...) == 3`; `:597-602` `state(c) == {... date(2026, 10, 20), 0, None, 0}` | PASS |
| C20 | P and R failed (attempts 1), S synced; `synced` 1, `failed` 2 | `-k one_failure_does_not_stop_others`: PASSED | `tests/test_nightly_sync.py:605` def; `:614-615` `nightly_attempts == 1`; `:617` `== date(2026, 10, 20)`; `:618` `counts["synced"] == 1`; `:619` `counts["failed"] == 2` | PASS |
| C21 | `main()` returns 0; the subprocess exits 0 within 60 s | `-k exit_zero`: PASSED | `tests/test_run_due.py:108` def; `:112` `assert main() == 0`; `:121` `result.returncode == 0`; `:101` `timeout=60` | PASS |
| C22 | exit 1 plus `jobs.run_failed`, for both an unreachable DB and an invalid key; no secrets | `-k exit_one_when_runner_cannot_start`: PASSED | `tests/test_run_due.py:127` def; `:134` `result.returncode == 1`; `:140` `len(failed) == 1`; `:141` `failed[0]["error_type"]`; `:142` `secret not in result.stdout + result.stderr` | PASS |
| C23 | the raising job is logged, the other job runs, exit 0 | `-k failing_job_does_not_stop_others`: PASSED | `tests/test_run_due.py:145` def; `:159` `main() == 0`; `:161` `len(ran) == 1`; `:167-169` `== [("raising_job", "ValueError")]` | PASS |
| C24 | `run_finished` counts 3/1/1/1; `sync_failed` fields | `-k run_finished_counts`: PASSED | `tests/test_run_due.py:208` def; `:219` `len(finished) == 1`; `:220-227` `{"due": 3, "synced": 1, "failed": 1, "skipped_locked": 1}`; `:229-234` `== [(str(plaid_failed.connection_id), "ITEM_ERROR", "ITEM_LOGIN_REQUIRED", "req-n1")]` | PASS |
| C25 | no tokens, `boom-secret` or `secret-name` in the logs; the RuntimeError line holds `error_type` only | `-k no_secrets_in_job_logs`: PASSED | `tests/test_run_due.py:237` def; `:250` `[value for value in leaks if value in logs] == []`; `:258` `== "RuntimeError"`; `:259-260` no `error_code` and no `request_id` | PASS |
| C26 | pool `checkedin()` is 0 after `main()` | `-k engine_disposed`: PASSED | `tests/test_run_due.py:263` def; `:268` `assert get_engine().pool.checkedin() == 0` | PASS |
| C27 | Sentry active and `register` done before the jobs run; inactive without a DSN | `-k main_sets_up_before_jobs`: PASSED | `tests/test_run_due.py:271` def; `:297` `seen == {"sentry": True, "registered": True}`; `:304` `seen["sentry"] is False` | PASS |
| C28 | recorder reached through `main()` and through the lifespan; `register` is idempotent | `-k subscriptions_reach_job_events`: PASSED | `tests/test_run_due.py:307` def; `:331-333` `== [("transactions.synced", c.business_id, 1)]`; `:345` `len(heard) == 1` (lifespan); `:354` `len(heard) == 1` (`register()` twice) | PASS |
| C29 | the `jobs` service has the shape doors 5 and 7 require | `proofs.sh c29`: printed `PASS c29` | `.specs/features/15-bank-nightly-sync-job/proofs.sh:44` `assert not missing`; `:45` no healthcheck or preDeploy; `:49` env refs equality; `:50` no other variables; `:52` `"jobs" in resources` | PASS |
| C30 | `railway config plan --detailed-exit-code` exits 0 | `proofs.sh c30`: printed `PASS c30` (read-only plan) | `.specs/features/15-bank-nightly-sync-job/proofs.sh:58-59` plan exit code, else `fail c30` | PASS |
| C31 | the newest staging `jobs` deployment logged `run_finished`, and it did not fail | `proofs.sh c31`: printed `PASS c31` (read-only list and logs) | `.specs/features/15-bank-nightly-sync-job/proofs.sh:70` status not FAILED or CRASHED; `:80` `'jobs.run_finished' in events`; `:81` `'jobs.run_failed' not in events` | PASS |
| C32 | the migration adds 4 columns and the check constraint, and the downgrade removes them | `-k nightly_state_upgrade_downgrade_and_check`: PASSED | `tests/test_migrations.py:551` def; `:589-592` column types and nullability; `:593` `tuple(existing) == (None, 0, None, 0)`; `:594` `"ck_bank_connections_failed_nights" in str(excinfo.value)`; `:606-614` `remaining.isdisjoint(...)`; `:615` constraint removed | PASS |
| C33 | ruff, mypy and the full pytest pass; `openapi.json` is unchanged | `proofs.sh c33`: ruff format, ruff check, mypy pass; full `pytest` 365 passed, 3 deselected (95.4 s); openapi export unchanged; printed `PASS c33` | `.specs/features/15-bank-nightly-sync-job/proofs.sh:87-88` `ruff format --check && ruff check && mypy app && pytest`; `:90-91` `git diff --exit-code -- contracts/openapi.json` | PASS |

### Findings (ranked)

1. **The tests depend on the wall clock (C1-C20, C24-C25; for example `tests/test_nightly_sync.py:121-149`).** This is a robustness gap and the most important finding here.
   - `new_connection` sets `created_at` only when a test passes one. Otherwise the row gets `server_default=func.now()` (`app/modules/bank_sync/models.py:71-72`).
   - The due rule (`app/modules/bank_sync/service.py:681`) skips any night at or before the night of `created_at`.
   - The simulated clocks are fixed dates: 2026-10-12 (C5), 2026-10-20 (C1, C2, C6-C20, C24, C25) and 2026-10-25 (C3). Every connection is created at the real current time.
   - So these proofs pass only while today is before those dates. C1's claim, "a connection created on 2026-10-05", holds today only by coincidence; the test never sets that date.
   - Expect `test_every_time_zone` to go red from about 2026-10-12, and most of S1-S4 from about 2026-10-20.
   - `due_now()` in `tests/test_run_due.py:78-80` does it correctly: it sets `created_at` relative to the current time. The fix is to give `new_connection` a fixed `created_at` earlier than every window, for example 2026-10-05.
   - Under `light` this does not fail a check, because each proof ran and passed at HEAD with the right assertion. It should be routed as fix work before 2026-10-12.
2. **C8 precision (re-judged; minor, non-blocking): `tests/test_nightly_sync.py:341-346`.** The claim says "every row each sync wrote" carries its connection's `business_id`. Only `bank_transactions` rows are asserted.
   - In this test the sync's page reuses each connection's pre-existing account (`page([c.account], ...)`, `:332`), so the only rows the sync *inserts* are transactions.
   - The account and connection rows are only updated, and their `business_id` comes from setup.
   - `len(stored) == 2` together with the per-business `any(...)` pins exactly one transaction to each business.
   - The gap is in the claim's wording ("every row"), not in the behaviour.
3. **C14 `snapshot` (re-judged; no gap): `tests/test_nightly_sync.py:509`.** `before` is taken in the same test (`:497`), so the expected value is readable in that test. The helper `tests/test_transaction_sync.py:217-254` compares every mapped column of the business's transactions and accounts, plus the connections' cursors. That matches "transactions, balances and cursor unchanged". Round 1's note is closed.
4. **C21 (note): `tests/test_run_due.py:101`.** "Within 60 seconds" is enforced by `subprocess.run(timeout=60)` raising, not by an assertion. That is acceptable.

**Level:** S1-S3 assert at the service layer through `run_due(now)`. S4 adds the process boundary: C21 and C22 run a subprocess. C31 is the only proof on staging. C11 and C13 use real Postgres locks from threads. Nothing here is a level gap for a job with no route.

**Sampling:** C3 and C4 check every hourly run in each 14-day window. C5 covers all 8 zones. C18 covers all 3 paths. No claim covers more cases than its proof runs.

## Coverage

Not recomputed under the `light` profile. `checks.md`'s Coverage table was read but not joined against the code.

## Faults injected

None injected under the `light` profile.

## Swept existing (re-read)

- **Validation, "time zones come from AD-029's check constraint":** present. `ck_businesses_time_zone` in `services/core/migrations/versions/a5405a43e4b4_create_businesses_and_memberships.py:52-55` lists the same 8 zones as `ALL_ZONES` (`tests/test_nightly_sync.py:41-50`).
- **Idempotency, "the sync itself is spec 14's idempotent `sync_connection` (spec 14 C11)":** present. It is `services/core/tests/test_transaction_sync.py:534` `test_second_sync_changes_nothing`, which ran green inside c33's full suite.
- **Concurrency, "row lock with `SKIP LOCKED`":** present in `services/core/app/modules/bank_sync/repository.py:198-205`, `.where(business_id == ..., id == ...).with_for_update(skip_locked=True)`.

## Gate

- Targeted pytest batch: **31 passed, 9 deselected**, exit 0, in 23.30 s.
- `bash .specs/features/15-bank-nightly-sync-job/proofs.sh c29 c30 c31 c33`: `PASS c29`, `PASS c30`, `PASS c31`, `PASS c33`, exit 0. Full API suite inside c33: 365 passed, 0 failed, 3 deselected
- 33 of 33 checks proven at HEAD `8071204`.
