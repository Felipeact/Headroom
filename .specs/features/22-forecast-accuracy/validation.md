# 22-forecast-accuracy Validation

**Date**: 2026-10-07
**Spec**: `.specs/features/22-forecast-accuracy/spec.md`
**Diff range**: `8f44b9c..14dfa67` (8 task commits: bdc481d, f466a14, d4f5e61, 369dfaa, b514249, 4b33d0b, a6f6ec6, 14dfa67)
**Verifier**: independent sub-agent (author ≠ verifier)

**Verdict**: PASS

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Expose the labeller | ✅ Done | `bank_sync.service.label_transactions` (pure wrapper over `labels.label_all`) |
| T2 Replay core | ✅ Done | `forecasting/backtest.py` |
| T3 Backtest command | ✅ Done | `main()`, argparse `--seed` |
| T4 Record the baseline | ✅ Done | `context/specs/22-forecast-accuracy.md` "Measured accuracy" |
| T5 Pin and accuracy tables | ✅ Done | models + migration `7a2f7dbe8d2f` |
| T6 Weekly pin and error recording | ✅ Done | `service.record_forecast_accuracy`, `_record_business`, `_Actuals` |
| T7 Register the job | ✅ Done | `JOBS = (nightly_bank_sync, forecast_accuracy)` |
| T8 Accuracy history | ✅ Done | `service.accuracy_history`, `AccuracyRecord` |

All tests below are under `services/core/`.

---

## Spec-Anchored Acceptance Criteria

### P1: Backtest the strategies on the sample data

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| ACC-01 no-args run | Seeds 0–4 × every strategy × horizons 1, 4, 13, each with mean %, mean $, worst %, origins | `tests/test_forecast_backtest.py:169` - seed headers `== ["0","1","2","3","4"]`; `:180-181` - `len(found) == 5 * 3`, `[r[1] for r in found] == ["1","4","13"] * 5` per strategy; `:198` - row columns `== [origins, zero_actual, mean%, worst%, $mean]` from `replay()`; `:235-236` - `uv run python -m app.modules.forecasting.backtest` exits 0 and prints `Seed 0` | ✅ PASS |
| ACC-02 `--seed N` | Only seed N | `tests/test_forecast_backtest.py:188` - `[l for l in lines if l.startswith("Seed")] == ["Seed 3"]` | ✅ PASS |
| ACC-03 known then | Only txns dated ≤ origin's today; balances reconstructed; patterns from that history; labels as of the day; no expected payments | `tests/test_forecast_backtest.py:40-41` - `len(inputs.transactions) == len(known)`, `max(t.date) <= today`; `:44-50` cash balances `== reference - later(...)`; `:53` card `== CARD_OWED_CENTS + later(visa)`; `:60` pattern txn ids ⊆ known ids; `:62` payroll `== [("biweekly", PAYROLL_CENTS)]`; `:65` `open_occurrences == ()`; `:72-75` internal_transfer label with a link; `tests/test_transaction_labels.py:886-890` - `on_day[lone.id] == ("in_transit", None)` then `later[lone.id] == ("normal", None)` | ✅ PASS |
| ACC-04 actual balance | Reference cash minus cash txns after the week's Sunday | `tests/test_forecast_backtest.py:83` - `actual_balance(sample, REFERENCE_DAY) == reference == 4_230_000`; `:85` - `== reference - later(sample, CASH, sunday)`; `:143` - `pairs[4] == (weeks[3].end_balance_cents, actual_balance(sample, monday + 3w6d))` | ✅ PASS |
| ACC-05 error formula | `abs(f − a) / abs(a) × 100` | `tests/test_forecast_backtest.py:95` - `mean_percent == approx((10 + 10 + 25) / 3)` over `(110,100),(90,100),(-50,-40)`; `:96` worst `== 25.0` | ✅ PASS |
| ACC-06 zero actual | Left out of the % mean; counted in `zero_actual` | `tests/test_forecast_backtest.py:94` - `zero_actual == 1`; `:95` mean excludes `(50, 0)`; `:98` cents mean still includes it (`== 20`) | ✅ PASS |
| ACC-07 deterministic | Identical output on two runs | `tests/test_forecast_backtest.py:133` - `backtest.replay(sample) == first`; plus repeatable check: two runs of `--seed 2` compared with `cmp`: IDENTICAL (`render` is a pure function of the scores) | ✅ PASS |
| ACC-08 bad seed | Exit 2 + usage message | `tests/test_forecast_backtest.py:207-213` - for `-1`, `x`, `1.5`: `exited.value.code == 2`, `"usage:" in err`; manual: `--seed -1` → rc=2, `usage: python -m app.modules.forecasting.backtest ...` | ✅ PASS |

### P1: Record the accuracy baseline

| Criterion | Spec-defined outcome | Evidence | Result |
| --- | --- | --- | --- |
| ACC-09 (docs) | Horizon-4 mean per strategy on seeds 0–4 under "Measured accuracy"; Done-when 1 unticked | `context/specs/22-forecast-accuracy.md:21-28` table vs fresh run of `uv run python -m app.modules.forecasting.backtest` (2026-10-07): recurring_pattern 22.55 / 21.56 / 21.02 / 21.73 / 19.68, rolling_average 20.96 / 20.93 / 21.96 / 20.93 / 18.49, 61 origins each — exact match. `context/specs/22-forecast-accuracy.md:18` - `- [ ]` (unticked) | ✅ PASS (repeatable check, no pytest by design) |
| ACC-10 | Dropped (context.md D5) | - | n/a |

### P1: Record real forecast errors each week

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| ACC-11 Monday pin | On/after business-local Monday 00:00, pin the latest snapshot to that Monday | `tests/test_forecast_accuracy.py:167` - Sunday 23:30 Toronto (Monday UTC) → `pins == {Sep 21: first}`; `:170` - Monday 00:30 → `{Sep 21: first, MONDAY: first}`; `tests/test_run_due.py:361` - `jobs.JOBS == (nightly.nightly_bank_sync, forecast_accuracy)` | ✅ PASS |
| ACC-12 no snapshot | No pin | `tests/test_forecast_accuracy.py:189` - `pins(bid) == {}` | ✅ PASS |
| ACC-13 record row | From Tuesday 00:00 after T; one row with all named fields; `error_cents = forecast − actual` | `tests/test_forecast_accuracy.py:203` - Mon 23:59 → `rows == {}`; `:207` - Tue 00:00 → `set(found) == {(MONDAY, 1)}`; `:210-219` - `(target_week_start, snapshot_id, currency) == (MONDAY, first, "CAD")`, `(forecast, actual, error) == (BASE+1, actual, BASE+1-actual)`; `:223-228` - h4 absent at Oct 26 23:00, present at Oct 27 01:00 with `target_week_start == Oct 19`, `error == BASE+4-800_000`; schema: `tests/test_migrations.py` `test_forecast_accuracy_upgrade_downgrade_and_check` | ✅ PASS |
| ACC-14 actual | Included CAD cash balances minus their txns after T's Sunday | `tests/test_forecast_accuracy.py:209` - `actual = 500_000 + 300_000 - (7_000 - 1_000)` (visa −5,000 and Oct 3 −20,000 not subtracted); `:286` param `excluded` → `500_000`; `null_balance` → `501_000` | ✅ PASS |
| ACC-15 missing week | No row for that horizon | `tests/test_forecast_accuracy.py:242-244` - stale snapshot: h1 `== BASE + 4`, h4 `== BASE + 7` (matched by Monday, not number), `(MONDAY, 13) not in found` | ✅ PASS |
| ACC-16 idempotent | No new pin, no new/changed row; unique keys | `tests/test_forecast_accuracy.py:257` - rerun `== {"pinned": 0, "recorded": 0, "accuracy_failed": 0}`; `:261-263` - after balance change, `(actual_cents, created_at)` unchanged; `:174` - newer snapshot does not replace the pin; migration test rejects duplicate pin and duplicate `(business, week, horizon)` with `IntegrityError` | ✅ PASS |
| ACC-17 failure isolated | Log `forecast.accuracy_failed` with business ID and error type only; continue | `tests/test_forecast_accuracy.py:335` - `counts == {"pinned": 1, "recorded": 1, "accuracy_failed": 1}`; `:337-340` broken rolled back, other recorded `actual == 200_000`; `:342-344` - `business_id == str(broken)`, `error_type == "RuntimeError"`, `"123456" not in out` | ✅ PASS |
| ACC-18 counts, no amounts | Returns `pinned`, `recorded`; logs no amounts | `tests/test_forecast_accuracy.py:298` - `settle(now) == {"pinned": 1, "recorded": 1, "accuracy_failed": 0}`; `:304-305` log line counts and `not [k for k in line if "cents" in k or "balance" in k]` | ✅ PASS |

### P1: Accuracy history for spec 32

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --- | --- | --- | --- |
| ACC-19 history | Horizon filter, week ≥ since, order (week, business), integer cents, currency, `error_percent` (null at 0) | `tests/test_forecast_accuracy_history.py:60` - `[(week, business)] == [(w2, a), (w2, b), (w3, a)]` (excludes h1 row and the w1 row); `:62-73` - full `AccuracyRecord(... error_cents=-30_000, error_percent=25.0)`; `:74` - `== approx(10.0)`; `:75` - `is None` at actual 0 | ✅ PASS |
| ACC-20 bad horizon | `ValueError` | `tests/test_forecast_accuracy_history.py:78-82` - horizons 0, 2, 5, 14 → `pytest.raises(ValueError)` | ✅ PASS |
| ACC-21 no route | No HTTP route | `tests/test_forecast_accuracy_history.py:88-89` - `not [p for p in paths if "accuracy" in p or "pin" in p]` | ✅ PASS |

**Status**: ✅ All 20 active ACs covered with spec-anchored assertions. No spec-precision gaps.

---

## Known deviations (judged)

1. **`accuracy_failed` instead of `failed`.** Accepted. ACC-18 requires only `pinned` and `recorded`; ACC-17 requires the failure to be logged, not counted. `jobs.run_finished` merges count keys across jobs and the nightly job already emits `failed`, so a distinct key avoids silently overwriting it. Recorded in AD-085.
2. **Null included balance → 501,000.** Accepted. ACC-14 defines actual = current balances − transactions after T's Sunday; the edge case says null counts as 0. Reserve: 0 − (−1,000.00 on Oct 7, after Sunday Oct 4) = +1,000.00, so 500,000 + 1,000 = 501,000 follows the formula exactly.

---

## Discrimination Sensor

Isolated scratch: `git worktree add <scratchpad>/wt 14dfa67`, own `uv sync`, `.env.local` copied. Unmutated baseline in the worktree: 29 passed. Each mutant applied alone, the relevant test file run with `-x`, file restored.

| # | File (in diff) | Mutation | Killed by | Result |
| --- | --- | --- | --- | --- |
| M1 | `app/modules/forecasting/backtest.py` `inputs_at` | `t.date <= today` → `<= today + 7 days` (future leaks in) | `test_inputs_known_then` | ✅ Killed |
| M2 | `backtest.py` | `WARM_UP_WEEKS = 13` → `12` | `test_replay` | ✅ Killed |
| M3 | `backtest.py` `score` | percent `/ abs(a)` → `/ abs(f)` | `test_score` | ✅ Killed |
| M4 | `backtest.py` `_due` | target Sunday `days=6` → `days=7` | `test_replay_matches_one_origin` | ✅ Killed |
| M5 | `backtest.py` `main` | `--seed` ignored (always SEEDS) | `test_command_one_seed` | ✅ Killed |
| M6 | `app/modules/forecasting/service.py` | `RECORD_AFTER` 8 days → 7 (Monday, not Tuesday) | `test_records_from_the_tuesday_after` | ✅ Killed |
| M7 | `service.py` `_Actuals` | `included` filter dropped | `test_records_from_the_tuesday_after` | ✅ Killed |
| M8 | `service.py` `_Actuals` | CAD currency filter dropped | - | ⚠️ Survived — equivalent (see below) |
| M9 | `app/modules/forecasting/repository.py` `add_pin` | `ON CONFLICT DO NOTHING` → `DO UPDATE SET snapshot_id` | `test_pins_latest_on_monday` | ✅ Killed |
| M10 | `service.py` `_record_business` | pin back-dated one week | `test_pins_latest_on_monday` | ✅ Killed |
| M11 | `service.py` | `error_cents` sign flipped (actual − forecast) | `test_records_from_the_tuesday_after` | ✅ Killed |
| M12 | `service.py` | missing target week falls back to week 1 instead of no row | `test_target_week_matched_by_monday` | ✅ Killed |
| M13 | `service.py` `record_forecast_accuracy` | `continue` → `raise` (one failure stops the job) | `test_one_failure_isolated` | ✅ Killed |
| M14 | `repository.py` `accuracy_rows` | order by business, then week | `test_accuracy_history` | ✅ Killed |
| M15 | `service.py` `accuracy_history` | horizon check weakened to `> 13` only | `test_accuracy_history_horizons[0]` | ✅ Killed |
| M16 | `repository.py` `accuracy_rows` | `week_start >= since` → `>` | `test_accuracy_history` | ✅ Killed |

**M8 judgment (equivalent mutant, not a test gap):** a non-CAD account cannot be included through product code. `bank_sync/service.py:282` sets `included` only for CAD checking on link, and `bank_sync/service.py:481-482` (`_cash_conflict` → `"currency"`) refuses to include a non-CAD account. So the state that would distinguish the mutant is unreachable without a raw DB write; the CAD check in `_Actuals` is defense in depth. Optional hardening (not required for PASS): plant an included USD account in `test_accounts_at_record_time`.

**Sensor depth**: expanded (16 manual mutations; P0-style because the job writes durable data-integrity rows)
**Result**: 15/15 non-equivalent mutants killed; 1 equivalent survived - ✅ PASS

**Isolation**: `git worktree remove --force` done, `git worktree list` shows only the main tree; `git status --porcelain` after == baseline (` M .agents/.skill-lock.json`, ` M .agents/.skill-lock.json.backup`, `?? .claude/skills/tlc-spec-driven/`). No stash used.

---

## Code Quality

| Principle | Status |
| --- | --- |
| Minimum code | ✅ No route, no UI, no tuning (`strategies.py` untouched), per Out of Scope |
| Surgical changes | ✅ Only forecasting, the jobs registry, one pure wrapper in `bank_sync/service.py`, migration, tests, docs |
| No scope creep | ✅ |
| Matches patterns | ✅ Cross-module access only through `bank_sync.service` / `accounts.service`; per-business transaction and logged-and-continue failure like the nightly job; write-once with `ON CONFLICT DO NOTHING`; Alembic-generated migration with named constraints; money as integer cents |
| Spec-anchored outcome check | ✅ Every asserted value is the spec's exact value, rebuilt independently in the tests |
| Per-layer coverage | ✅ Domain ACs 1:1; job happy, boundary (Monday 23:59 vs Tuesday 00:00), stale-snapshot, rerun, failure paths |
| Every test maps to a requirement | ✅ All 32 in-scope tests cite an ACC id or a spec edge case |
| Documented guidelines followed | ✅ `AGENTS.md` (module boundaries, money, tenancy note: `accuracy_history` is an intentional job-only cross-business read, AD-086; no secrets/amounts in logs) |

---

## Edge Cases

- [x] Included accounts change between pin and record → record-time accounts (`test_accounts_at_record_time[excluded]`)
- [x] Null included balance counts as 0 (`test_accounts_at_record_time[null_balance]`)
- [x] Downtime spanning weeks → only the current week pinned, no back-dating (`test_forecast_accuracy.py:177-182`); every due row recorded in one run (`test_target_week_matched_by_monday`, h1 and h4 at Dec 29)
- [x] Business-local Monday vs UTC (`test_forecast_accuracy.py:164-167`, Toronto Sunday 23:30)
- [x] History shorter than warm-up → 0 origins, no failure (`test_forecast_backtest.py:149-158`, `test_score_empty`)

---

## Gate Check

- **Static gate** (`services/core`): `uv run ruff format --check . && uv run ruff check . && uv run mypy app` → exit 0 (115 files formatted, all checks passed, mypy: no issues in 48 source files)
- **Tests**: `uv run pytest tests/test_forecast_backtest.py tests/test_forecast_accuracy.py tests/test_forecast_accuracy_history.py tests/test_transaction_labels.py::test_label_transactions_as_of_a_day tests/test_migrations.py::test_forecast_accuracy_upgrade_downgrade_and_check tests/test_run_due.py::test_jobs_registered -q` → **32 passed, 0 failed, 0 skipped** (1 unrelated Starlette deprecation warning)
- **Test count delta**: +32 new tests in scope (14 backtest, 9 job, 6 history, 1 labels, 1 migration, 1 jobs registry); no existing test removed or weakened in the diff
- **Full suite**: not run by the Verifier (in-scope files only, as permitted)
- **Failures**: none

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| --- | --- | --- |
| ACC-01 … ACC-09 | Verified | ✅ Verified (re-confirmed) |
| ACC-10 | Dropped | Dropped |
| ACC-11 … ACC-21 | Implemented | ✅ Verified |

(The Verifier does not edit `spec.md`; the orchestrator should apply this update.)

---

## Summary

**Overall**: ✅ Ready

**Spec-anchored check**: 20/20 active ACs matched the spec outcome; 0 spec-precision gaps
**Sensor**: 16 mutations, 15 killed, 1 survived (equivalent, M8)
**Gate**: static gate exit 0; 32 passed

**What works**: the backtest command and its replay rules, the recorded baseline (exact match to a fresh run, Done-when 1 unticked), weekly pins and write-once accuracy rows on business-local time, failure isolation, and the history reader for spec 32.

**Issues found**: none blocking. Optional: add an included non-CAD account to `test_accounts_at_record_time` so the CAD filter in `_Actuals` is discriminated if the bank_sync invariant ever loosens.

**Lessons**: none recorded. The only signal is M8, an equivalent mutant guarded by bank_sync's inclusion invariant, not a weak test, so there is no grounded execution lesson.

**validate_state.py**: `python .claude/skills/tlc-spec-driven/scripts/validate_state.py 22-forecast-accuracy` → `validate_state: 0 error(s) across [22-forecast-accuracy]`, exit 0.
