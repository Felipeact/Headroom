# 15 - Nightly sync job verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 625ae6a..6143979
**Round**: 3 - scoped
**Verifier**: independent sub-agent (author != verifier)

Round 3 re-verifies the fix for round 2's first-ranked finding: the nightly tests depended on the wall clock. The fix is commit `004dc46`. `git diff --stat 8071204..6143979` shows exactly one code file changed, `services/core/tests/test_nightly_sync.py` (+4 / -2). The other three files are docs: `.specs/STATE.md`, this report, and `context/token-usage/token-usage.md`. No app code, migration, `test_run_due.py`, `test_migrations.py` or `proofs.sh` changed.

All 33 proofs were re-run in full at HEAD `6143979` on 2026-10-06 UTC (2026-10-05 local), against the local Postgres on port 5432. Before the run, `get_engine().connect()` returned `select 1` = `1`. All 33 passed. The date gap is closed (see "Date gap" below).

## Binding sources

Carried from 8071204. Not run under `light`; step 1 runs only under `ui`. This spec has no screen and no route (plan `Surface`: none), and the fix touched no interface. The "Done when" items in `context/specs/15-bank-nightly-sync-job.md` map to C3, C4 (Pacific and Newfoundland on a simulated clock) and C10-C12 (overlapping runs).

## Date gap (round 2 finding 1) - verified at 6143979

The fix, `004dc46`:
- adds `CREATED_AT = datetime(2026, 10, 5, 12, tzinfo=ZoneInfo("UTC"))` at `tests/test_nightly_sync.py:52`
- makes `new_connection` always set `connection.created_at = created_at or CREATED_AT` (`tests/test_nightly_sync.py:148`). Before, it set `created_at` only when a test passed one, so the row kept `server_default=func.now()` (`app/modules/bank_sync/models.py:71-72`)

Why this closes the gap:
- **The only wall-clock input to the due rule was `created_at`.** `_nightly_due` (`app/modules/bank_sync/service.py:678-690`) reads `night_of(now)`, which comes from the simulated `now`; `night_of(connection.created_at)`, which is now pinned; and `nightly_synced_on` and `next_nightly_attempt_at`, which are written only from the simulated `now`.
- **The pinned date falls before every window.** `CREATED_AT` is 2026-10-05 08:00 in Toronto and 08:30 in St. John's, so its night is 2026-10-05 in every AD-029 zone. The earliest simulated night is 2026-10-11 (C5's `start` 2026-10-12T00:00Z, `:296`). The others are 2026-10-20 (C1, C2, C6, C8-C20, C24, C25), 2026-10-24/25 (C3) and 2027-03-06/07 (C4). C7 passes its own `created_at` (`:319`).
- **C1's precondition is now literally true.** The check says "a connection created on 2026-10-05", and the test now creates it on that date instead of relying on today being 2026-10-05.
- **No other wall-clock reads.** A search of `tests/test_nightly_sync.py` and `tests/test_run_due.py` for `today(`, `now(`, `utcnow`, `time.time` and `func.now` finds only:
  - `test_run_due.py:80` `due_now()`, which is `datetime.now(UTC) - timedelta(days=3)`. It is paired with `main()`, which runs `run_due(datetime.now(UTC))` (`app/jobs/run_due.py:54`), so the connection is always 3 nights old whatever the date. This holds at any hour too, because the due rule compares only night dates.
  - `import time` in `test_nightly_sync.py:12`, used for `time.monotonic()` elapsed time in C10 (`:388`). That is not a date.
- **`func.now()` in the app does not feed the due rule.** It appears only in `updated_at` writes (`service.py:513`, `:534`) and other column defaults.
- **The C24 and C25 tests are fixed too.** `mixed_run` in `tests/test_run_due.py:172-190` calls `new_connection(TORONTO)` with no `created_at`, so it now gets `CREATED_AT`, and those runs are at `utc(2026, 10, 20, 6)`.

**Demonstration.** Neither `freezegun` nor `time-machine` is installed (`uv pip list` shows neither), and neither could fake Postgres's `now()`, which was the actual source of the date. Creating a worktree to inject a later date needs the user's approval (AGENTS.md), so it was not done. The evidence above is by reasoning, with file:line citations. The pinned path is visible at `:148`, and no remaining path reads the date.

**Side effect checked:** every connection in these tests now has the same `created_at`, so `nightly_candidates`' `order_by(created_at, id)` (`app/modules/bank_sync/repository.py:185`) falls back to the random UUID `id`. No test asserts processing order:
- C11, C20, C24 and C25 assert per connection or by count, and C11 holds under either thread order.
- The batch passed. The full suite in c33 ran these tests a second time.

## Checks

Verified at 6143979. The pytest proofs ran in one invocation from `services/core`: `uv run pytest tests/test_nightly_sync.py tests/test_run_due.py tests/test_migrations.py -p no:logging -v -k "<the 29 selectors joined with or>"`. It exited `0`, with **31 passed, 9 deselected** in 61.59 s. Each test is listed individually as PASSED, and C18 runs 3 parameters.

Command proofs ran from the repo root: `bash .specs/features/15-bank-nightly-sync-job/proofs.sh c29 c30 c31 c33`.

`tests/test_nightly_sync.py` citations were refreshed at 6143979 with `rg -n "^def test_|assert "`. The fix moved every line from `CREATED_AT` onward by +2; each cited line was re-read. `tests/test_run_due.py`, `tests/test_migrations.py` and `proofs.sh` are unchanged since 8071204, so their citations are carried from 8071204.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | Toronto connection created 2026-10-05, synced once at 2026-10-20T06:00Z, `nightly_synced_on` 2026-10-20 | `-k due_connection_synced_once`: PASSED | `tests/test_nightly_sync.py:238` def; `:52` `CREATED_AT` 2026-10-05 via `:148`; `:243` `assert fake.times(c.token) == [utc(2026, 10, 20, 6)]`; `:244` `assert state(c)["nightly_synced_on"] == date(2026, 10, 20)` | PASS |
| C2 | no sync 07:00Z-05:00Z after C1 | `-k not_again_same_night`: PASSED | `tests/test_nightly_sync.py:247` def; `:251` `hourly(utc(2026, 10, 20, 7), utc(2026, 10, 21, 5))` (inclusive, `:192-197`); `:254` `assert fake.times(c.token) == [utc(2026, 10, 20, 6)]` | PASS |
| C3 | fall-back window: 14 syncs each, Vancouver 02:00 (09:00Z), St_Johns 02:30 | `-k fall_back_window`: PASSED | `tests/test_nightly_sync.py:257` def; `:265` `days` = 14 dates from 2026-10-25; `:266-268` Vancouver `local(VANCOUVER, ..., 2, 0) for d in days`; `:269-271` St_Johns `..., 2, 30`; `:273` `== [9] * 14` | PASS |
| C4 | spring-forward window: 14 each; St_Johns 03:30 on 2027-03-14, otherwise 02:30; Vancouver 02:00 | `-k spring_forward_window`: PASSED | `tests/test_nightly_sync.py:276` def; `:284-285` days and `spring = date(2027, 3, 14)`; `:286-288` Vancouver `local(VANCOUVER, ..., 2, 0)`; `:289-292` `local(ST_JOHNS, ..., 3 if d == spring else 2, 30)` | PASS |
| C5 | all 8 AD-029 zones, synced once each night 2026-10-12, 13, 14 | `-k every_time_zone`: PASSED | `tests/test_nightly_sync.py:295` def; `:41-50` `ALL_ZONES` (8); `:297` one connection per zone; `:304` `assert nights == [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)]` | PASS |
| C6 | catch-up at 07:00 local (11:00Z), `nightly_synced_on` 2026-10-20 | `-k catch_up_later_same_night`: PASSED | `tests/test_nightly_sync.py:309` def; `:314` `== [utc(2026, 10, 20, 11)]`; `:315` `== date(2026, 10, 20)` | PASS |
| C7 | created 15:00 local waits until 02:00 | `-k created_tonight_waits`: PASSED | `tests/test_nightly_sync.py:318` def; `:319` `created_at=utc(2026, 10, 20, 19)`; `:323` `assert fake.times(c.token) == []`; `:326` `== [utc(2026, 10, 21, 6)]` | PASS |
| C8 | each sync's rows carry their own business's `business_id` | `-k each_sync_scoped_to_its_business`: PASSED | `tests/test_nightly_sync.py:329` def; `:343` `assert len(stored) == 2`; `:345-348` `any(business == c.business_id and pid.startswith(...))` per connection | PASS |
| C9 | one cross-business read, single caller in `service.py` | `-k one_cross_business_read`: PASSED | `tests/test_nightly_sync.py:351` def; `:361` `assert unscoped == ["connection_for_item", "nightly_candidates"]`; `:369` `== ["modules/bank_sync/service.py"]` | PASS |
| C10 | locked connection skipped in under 5 s, `skipped_locked` 1, null `nightly_synced_on`, synced at the next run | `-k locked_connection_skipped`: PASSED | `tests/test_nightly_sync.py:376` def; `:388` `< 5`; `:389` `== []`; `:390` `counts["skipped_locked"] == 1`; `:391` `is None`; `:397` `== [utc(2026, 10, 20, 7)]` | PASS |
| C11 | concurrent runs: 1 call per connection, both nights set, `synced` sum 2 | `-k concurrent_runs_sync_once`: PASSED | `tests/test_nightly_sync.py:400` def; `:417` `fake.entered.wait(10)` before the 2nd thread starts; `:425-426` `len(...) == 1`; `:427-428` `== date(2026, 10, 20)`; `:429` `sum(s["synced"] for s in summaries) == 2` | PASS |
| C12 | a second run at the same `now`: no call, `due` 0 | `-k second_run_sees_finished_night`: PASSED | `tests/test_nightly_sync.py:432` def; `:439` `== [now]`; `:440` `counts["due"] == 0` | PASS |
| C13 | NOWAIT fails during the sync; same `xmin` | `-k outcome_in_sync_transaction`: PASSED | `tests/test_nightly_sync.py:443` def; `:460` `isinstance(excinfo.value.orig, LockNotAvailable)`; `:476` `connection_xmin == transaction_xmin` | PASS |
| C14 | attempts 1/2/3, next attempt 03:00/05:00/09:00 local, data unchanged | `-k retry_delays_grow`: PASSED | `tests/test_nightly_sync.py:497` def; `:499` `before = snapshot(...)`; `:501-505` expected table; `:509` `nightly_attempts == attempts`; `:510` `next_nightly_attempt_at == next_at`; `:511` `snapshot(c.business_id) == before` | PASS |
| C15 | calls at exactly 02, 03, 05, 09 local | `-k no_attempt_before_next_attempt_time`: PASSED | `tests/test_nightly_sync.py:514` def; `:522-524` `local_times(fake, c) == [local(TORONTO, 2026, 10, 20, h) for h in (2, 3, 5, 9)]` | PASS |
| C16 | 4th failure ends the night; next night starts at 02:00 | `-k fourth_failure_ends_night`: PASSED | `tests/test_nightly_sync.py:527` def; `:532-537` `state(c) == {"nightly_synced_on": date(2026, 10, 20), "nightly_attempts": 0, "next_nightly_attempt_at": None, "failed_nights": 1}`; `:543` `[4:] == [local(TORONTO, 2026, 10, 21, 2)]` | PASS |
| C17 | `needs_attention` F, F, T at `failed_nights` 1, 2, 3 | `-k three_failed_nights_need_attention`: PASSED | `tests/test_nightly_sync.py:546` def; `:556` `assert seen == [(1, False), (2, False), (3, True)]` | PASS |
| C18 | success on either path clears; a failure keeps 3 | `-k success_clears_attention`: 3 params PASSED | `tests/test_nightly_sync.py:559-561` parametrize `["sync_connection", "nightly", "sync_connection_fails"]`; `:584` `failed_nights == 3`; `:587` `== 0`; `:588` `needs_attention(c) is False` | PASS |
| C19 | success at 05:00 after 2 failures ends the night | `-k success_after_retries_ends_night`: PASSED | `tests/test_nightly_sync.py:591` def; `:598` `len(...) == 3`; `:599-604` `state(c) == {... date(2026, 10, 20), 0, None, 0}` | PASS |
| C20 | P and R failed (attempts 1), S synced; `synced` 1, `failed` 2 | `-k one_failure_does_not_stop_others`: PASSED | `tests/test_nightly_sync.py:607` def; `:616-617` `nightly_attempts == 1`; `:619` `== date(2026, 10, 20)`; `:620` `counts["synced"] == 1`; `:621` `counts["failed"] == 2` | PASS |
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
| C33 | ruff, mypy and the full pytest pass; `openapi.json` is unchanged | `proofs.sh c33`: ruff format, ruff check, mypy pass; full `pytest` 365 passed, 3 deselected (191.68 s); openapi export unchanged; printed `PASS c33` | `.specs/features/15-bank-nightly-sync-job/proofs.sh:87-88` `ruff format --check && ruff check && mypy app && pytest`; `:90-91` `git diff --exit-code -- contracts/openapi.json` | PASS |

### Findings (ranked)

1. **Round 2 finding 1, the wall-clock dependency: closed at `004dc46`.** See "Date gap" above. No date or time-of-day dependency remains in the 31 pytest proofs.
2. **C8 precision (carried; minor, non-blocking): `tests/test_nightly_sync.py:343-348`.** The claim says "every row each sync wrote" carries its connection's `business_id`. Only `bank_transactions` rows are asserted.
   - The sync's page reuses each connection's pre-existing account (`page([c.account], ...)`, `:334`), so the only rows the sync inserts are transactions.
   - `len(stored) == 2` with the per-business `any(...)` pins one transaction to each business.
   - The gap is in the claim's wording, not in the behaviour.
3. **C21 (carried note): `tests/test_run_due.py:101`.** "Within 60 seconds" is enforced by `subprocess.run(timeout=60)` raising, not by an assertion. That is acceptable.
4. **New, informational:** all test connections now share one `created_at`, so the candidate order inside a run is set by the random UUID `id` (`repository.py:185`). No proof depends on that order (see "Date gap"). This is not a gap.

**Level:** carried from 8071204, since the fix changed only a test helper's input. S1-S3 run at the service layer through `run_due(now)`. C21 and C22 cross the process boundary. C31 is on staging. C11 and C13 use real Postgres locks.

**Sampling:** carried from 8071204. C3 and C4 check every hourly run in their windows. C5 covers all 8 zones, and C18 covers all 3 paths.

## Coverage

Carried from 8071204. Not recomputed under the `light` profile.

## Faults injected

Carried from 8071204. None injected under the `light` profile.

## Swept existing (re-read)

Carried from 8071204. The fix touched none of these files.
- **Validation:** `ck_businesses_time_zone` in `services/core/migrations/versions/a5405a43e4b4_create_businesses_and_memberships.py:52-55` lists the same 8 zones as `ALL_ZONES` (`tests/test_nightly_sync.py:41-50`, re-read at 6143979).
- **Idempotency:** `services/core/tests/test_transaction_sync.py:534` `test_second_sync_changes_nothing`. It ran green inside c33's full suite at 6143979.
- **Concurrency:** `services/core/app/modules/bank_sync/repository.py:198-205`, `.with_for_update(skip_locked=True)` with a `business_id` filter.

## Gate

Verified at 6143979.
- Targeted pytest batch: **31 passed, 9 deselected**, exit 0, in 61.59 s.
- `bash .specs/features/15-bank-nightly-sync-job/proofs.sh c29 c30 c31 c33`: `PASS c29`, `PASS c30`, `PASS c31`, `PASS c33`, exit 0. Full API suite inside c33: 365 passed, 0 failed, 3 deselected
- 33 of 33 checks proven at HEAD `6143979`.
