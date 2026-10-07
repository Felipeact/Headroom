# Forecast Accuracy Specification

Spec: `context/specs/22-forecast-accuracy.md`. Depends on 21 (Done). User decisions: [context.md](context.md).

## Problem Statement

Spec 21 forecasts 13 weeks, but nothing measures how close those forecasts come to what actually happens. Without a number, a change to a strategy can't be judged better or worse, and spec 32's weekly report has no forecast error to show. This spec adds two measurements: a backtest that replays the sample data, and a weekly record of how real forecasts compared with real balances.

## Goals

- [ ] `uv run python -m app.modules.forecasting.backtest` reports the mean error at 1, 4 and 13 weeks for every registered strategy on the Harbor Street sample data.
- [ ] The measured 4-week error of `recurring_pattern` on seeds 0–4 is recorded as the baseline. Meeting ±10% waits for the sample realignment follow-up (context.md D5).
- [ ] Each week, every business's earlier forecasts are compared with its actual balance, and the errors are stored so spec 32 can read them.

## Out of Scope

| Feature | Reason |
| --- | --- |
| An HTTP endpoint or screen for accuracy | Spec 32's report reads the history from the service. No spec asks for a route or UI, and a route would add generated files and an auth surface for nothing. |
| The weekly metrics report itself | Spec 32 builds it. |
| Horizons other than 1, 4 and 13 weeks | The spec names these three. |
| Backtesting real customer data | Only synthetic data may be used (AGENTS.md). |
| Per-account accuracy | Forecasts are for combined cash. Account shortfall is in `specs/later/`. |
| Deleting old snapshots or accuracy rows | No retention rule exists yet. The rows are small. |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Pass rule (D1, D5) | The metric is the mean absolute percentage error at horizon 4. Spec 22 measures it and gates nothing on it. Done-when 1 stays unticked | The sample's noise floor is 14–18% (context.md) | y |
| Strategy tuning (D2, D5) | None in spec 22. `strategies.py` is unchanged | Tuning toward an unreachable bar would fit random draws | y |
| Which forecast counts in production (D3) | Weekly pin of the snapshot that is current at the start of the business-local Monday | Snapshots are reused (AD-077), so `last_computed_at` can't say what was current earlier | y |
| Seeds (D4) | The default run reports seeds 0–4; `--seed N` runs one | Guards against reading too much into one random draw | y |
| Error formula | `error_cents = forecast − actual`; percentage = `abs(error_cents) / abs(actual) × 100`. Rows store cents only, and `accuracy_history` derives the percentage | The ±10% rule is relative to the actual balance; a stored percentage would duplicate the cents | y |
| Actual balance of 0 | Excluded from the percentage mean and counted as `zero_actual`. Cents error is still recorded | Percentage is undefined | n |
| Backtest origins | Every Monday from `FIRST_DAY` + 13 weeks up to the last Monday whose horizon-h week ends on or before `REFERENCE_DAY`. Each horizon is averaged over its own origins | 13 weeks matches `MAX_HISTORY_WEEKS`; actuals must exist | n |
| Backtest "known then" | Only facts dated on or before the origin's business-local today count. Transactions are those dated on or before it. Cash and card balances are the reference balances minus transactions dated after it. Patterns are re-detected from that history. Labels are computed as of that day. No expected payments, because every sample expected payment is dated after `REFERENCE_DAY`. The origin's today is the Saturday before the Monday | The spec says "using only what was known then"; Saturday mirrors `REFERENCE_DAY`, a Saturday | n |
| Backtest actual balance | Reference cash balance minus cash-account transactions dated after the target week's Sunday | The fixture holds only end balances (AD-068) | n |
| Backtest runs without a database | Pure, in memory, through the strategies' pure seam (AD-078) | Fast, repeatable, safe to run anywhere | n |
| Production target week | For a pin made on Monday M and horizon h, the target week starts on M + 7(h − 1) days. The pinned snapshot's week whose `starts_on` equals that Monday is compared. If the snapshot has no such week (stale `as_of`), no row is written for that horizon | A stale snapshot's numbering doesn't line up with the pin week | n |
| Production actual balance | Included CAD cash accounts' current balances minus their transactions dated after the target Sunday, computed when the error is recorded | Same reconstruction as the backtest; no balance history is stored | n |
| When an error is recorded | On the first job run at or after Tuesday 00:00 business-local following the target week. Written once, never updated | Gives late-posting transactions a night to arrive; one row keeps history stable | n |
| Where the job runs | A new entry in `JOBS` (AD-056), hourly, idempotent | The existing hourly runner | n |
| History accessor for spec 32 | `forecasting.service.accuracy_history(session, *, horizon, since)` returns stored rows across businesses. It is internal: no route. | Spec 32's report runs as a job, like `nightly_candidates` (AD-053) | n |

**Open questions:** none. All are resolved or logged above. Rows marked `n` are defaults the user accepted by asking to build (2026-10-07).

---

## User Stories

### P1: Backtest the strategies on the sample data ⭐ MVP

**User Story**: As a developer changing the forecast, I want one command that reports each strategy's error at 1, 4 and 13 weeks, so I can tell with numbers whether a change helped.

**Why P1**: AGENTS.md requires the backtest's before/after numbers on every forecasting change, and the first Done-when item depends on it.

**Acceptance Criteria**:

1. WHEN `uv run python -m app.modules.forecasting.backtest` runs with no arguments THEN the backtest SHALL print, for each of seeds 0–4 and each registered strategy, the mean absolute percentage error, mean absolute error in dollars, worst percentage error and origin count at horizons 1, 4 and 13. <!-- ACC-01 -->
2. WHEN the command runs with `--seed N` THEN the backtest SHALL report only seed N. <!-- ACC-02 -->
3. WHEN the backtest forecasts from an origin THEN the backtest SHALL build the strategy's inputs only from transactions dated on or before the origin's today, balances reconstructed to that day, and patterns detected from that history. <!-- ACC-03 -->
4. The backtest SHALL compute the actual balance of a target week as the reference cash balance minus cash-account transactions dated after that week's Sunday. <!-- ACC-04 -->
5. The backtest SHALL compute each origin's error as `abs(forecast − actual) / abs(actual) × 100` for the target week's end balance. <!-- ACC-05 -->
6. IF a target week's actual balance is 0 THEN the backtest SHALL leave that origin out of the percentage mean and report it in a `zero_actual` count. <!-- ACC-06 -->
7. WHEN the backtest runs twice with the same seed THEN the backtest SHALL print identical output. <!-- ACC-07 -->
8. IF `--seed` is not a non-negative integer THEN the command SHALL exit with code 2 and a usage message. <!-- ACC-08 -->

**Independent Test**: Run the command and see a table of 5 seeds × 2 strategies × 3 horizons. A pytest builds the inputs for one origin and asserts that no transaction on or after the origin is present.

---

### P1: Record the accuracy baseline ⭐ MVP

**User Story**: As the product owner, I want the default forecast's measured 4-week error recorded, so the gap to the ±10% target is known and later changes are compared with it.

**Why P1**: This is the spec's first Done-when item, re-scoped by context.md D5. The item stays unticked until the sample realignment follow-up.

**Acceptance Criteria**:

1. WHEN spec 22 is built THEN the spec file `context/specs/22-forecast-accuracy.md` SHALL record the backtest's horizon-4 mean for each strategy on seeds 0–4, under a "Measured accuracy" heading, with Done-when 1 left unticked. <!-- ACC-09 -->

**Independent Test**: Run the backtest and compare its horizon-4 means with the recorded table.

---

### P1: Record real forecast errors each week ⭐ MVP

**User Story**: As the product owner, I want each business's earlier forecasts compared with its actual balances every week, so spec 32 can report real forecast error.

**Why P1**: This is the spec's second Done-when item.

**Acceptance Criteria**:

1. WHEN the hourly job runs on or after a business's local Monday 00:00 and that week has no pin THEN the job SHALL pin the business's latest forecast snapshot to that Monday. <!-- ACC-11 -->
2. IF the business has no forecast snapshot at that time THEN the job SHALL write no pin for that week. <!-- ACC-12 -->
3. WHEN the job runs on or after the business-local Tuesday 00:00 following target week T, and a pin made on Monday M has T = M + 7(h − 1) days for h in {1, 4, 13}, THEN the job SHALL store one accuracy row: `business_id`, pin Monday, horizon, target Monday, `snapshot_id`, currency, forecast end balance, actual balance, and `error_cents` = forecast − actual. <!-- ACC-13 -->
4. The job SHALL compute the actual balance as the included CAD cash accounts' current balances minus their transactions dated after T's Sunday. <!-- ACC-14 -->
5. IF the pinned snapshot has no week starting on T's Monday THEN the job SHALL store no row for that horizon. <!-- ACC-15 -->
6. WHEN the job runs again for a week it already handled THEN the job SHALL write no new pin and no new or changed accuracy row (unique on business, pin Monday and horizon). <!-- ACC-16 -->
7. IF recording one business fails THEN the job SHALL log `forecast.accuracy_failed` with the business ID and error type only, and continue with the other businesses. <!-- ACC-17 -->
8. WHEN the job finishes THEN the job SHALL return counts `pinned` and `recorded` (AD-056) and log no amounts. <!-- ACC-18 -->

**Independent Test**: With a fake clock, create a snapshot, run the job on Monday (pin), add transactions, advance past the target Tuesday, and run it again. Assert one row whose error equals the forecast minus the reconstructed actual. Run it a third time and assert nothing changed.

---

### P1: Accuracy history for spec 32 ⭐ MVP

**User Story**: As the builder of spec 32, I want a function that returns the stored errors, so the weekly report can show the 4-week forecast error without reading another module's tables.

**Why P1**: This is the spec's second Done-when item.

**Acceptance Criteria**:

1. WHEN `forecasting.service.accuracy_history(session, horizon=h, since=d)` is called THEN it SHALL return every stored row with that horizon and pin Monday ≥ d, ordered by pin Monday, then `business_id`, with integer-cent amounts, the currency, and `error_percent` = `abs(error_cents) / abs(actual) × 100` (null when actual is 0). <!-- ACC-19 -->
2. IF `horizon` is not 1, 4 or 13 THEN `accuracy_history` SHALL raise `ValueError`. <!-- ACC-20 -->
3. The accuracy tables SHALL have no HTTP route. <!-- ACC-21 -->

**Independent Test**: Store rows for two businesses and horizons 1 and 4. Call `accuracy_history(horizon=4, since=…)` and assert it returns only the horizon-4 rows, in order.

---

## Edge Cases

- IF a business's included accounts change between the pin and the record THEN the actual SHALL use the accounts included at record time (ACC-14). The row is still written once.
- IF an included account's `balance_cents` is null THEN it SHALL count as 0, as in `opening_balance` (spec 21).
- WHEN the job first runs after downtime spanning several weeks THEN it SHALL pin only the current week and SHALL record every due row whose pin exists. Missed weeks get no back-dated pin.
- WHEN a business's time zone makes its Monday start earlier or later than UTC THEN pins and record times SHALL follow the business-local day (AD-029, AD-082).
- WHEN the history is shorter than the 13-week warm-up THEN the backtest SHALL report `0` origins for that seed and horizon, not fail.

---

## Implicit-requirement dimensions

| Dimension | Coverage |
| --- | --- |
| Input validation & bounds | ACC-08 (`--seed`), ACC-20 (horizon) |
| Failure / partial failure | ACC-17: one business's failure is isolated |
| Idempotency / retry | ACC-16: unique keys; the job is safe to run twice (AGENTS.md) |
| Auth boundaries | ACC-21: no route. `accuracy_history` is a job-only cross-business read, like AD-053 |
| Concurrency / ordering | Two job runs at once: unique constraints plus insert-if-absent make the second a no-op (ACC-16) |
| Data lifecycle | Rows are kept indefinitely (Out of Scope). Pins reference snapshots, which are never deleted in v1 |
| Observability | ACC-17, ACC-18: counts and error types, no amounts |
| External-dependency failure | N/A because the job reads only our own database; Plaid is not called |
| State-transition integrity | N/A because pins and rows are write-once; there are no transitions |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| ACC-01 | P1: Backtest | Execute | Verified |
| ACC-02 | P1: Backtest | Execute | Verified |
| ACC-03 | P1: Backtest | Execute | Verified |
| ACC-04 | P1: Backtest | Execute | Verified |
| ACC-05 | P1: Backtest | Execute | Verified |
| ACC-06 | P1: Backtest | Execute | Verified |
| ACC-07 | P1: Backtest | Execute | Verified |
| ACC-08 | P1: Backtest | Execute | Verified |
| ACC-09 | P1: Accuracy baseline | Execute | Verified |
| ACC-10 | (dropped: no tuning, context.md D5) | - | Dropped |
| ACC-11 | P1: Weekly errors | Execute | Implemented |
| ACC-12 | P1: Weekly errors | Execute | Implemented |
| ACC-13 | P1: Weekly errors | Execute | Implemented |
| ACC-14 | P1: Weekly errors | Execute | Implemented |
| ACC-15 | P1: Weekly errors | Execute | Implemented |
| ACC-16 | P1: Weekly errors | Execute | Implemented |
| ACC-17 | P1: Weekly errors | Execute | Implemented |
| ACC-18 | P1: Weekly errors | Execute | Implemented |
| ACC-19 | P1: History | Execute | Implemented |
| ACC-20 | P1: History | Execute | Implemented |
| ACC-21 | P1: History | Execute | Implemented |

**Coverage:** 20 active (ACC-10 dropped), 20 mapped to tasks, 0 unmapped.

---

## Success Criteria

- [ ] Spec 22 Done-when 1: deferred to the sample realignment follow-up (context.md D5). The baseline is recorded (ACC-09).
- [ ] Spec 22 Done-when 2: `accuracy_history(horizon=4, …)` returns stored weekly errors, proven by the ACC-13 and ACC-19 tests.
- [ ] Every later forecasting commit can quote the backtest table before and after.
