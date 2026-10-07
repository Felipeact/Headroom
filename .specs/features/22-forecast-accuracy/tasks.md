# Forecast Accuracy Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/22-forecast-accuracy/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec. Guidelines found: `AGENTS.md` (Testing; "Before you finish a task"), `services/core/pyproject.toml` (pytest, ruff, mypy), `.github/workflows/ci.yml`.

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| --- | --- | --- | --- | --- |
| Pure domain (`backtest.py`, `labels` wrapper) | unit | Every AC 1:1; edge cases (short history, zero actual, bad seed) | `services/core/tests/test_forecast_backtest.py`, `tests/test_transaction_labels.py` | `uv run pytest tests/<file> -q` |
| Service + repository (`record_forecast_accuracy`, `accuracy_history`) | integration (local Postgres) | Every AC 1:1, plus idempotency, failure isolation and the edge cases | `services/core/tests/test_forecast_accuracy.py` | `uv run pytest tests/test_forecast_accuracy.py -q` |
| Models / migration | integration via the existing `test_migrations.py` | Upgrade to head works; constraint names follow AD-003 | `services/core/tests/test_migrations.py` | `uv run pytest tests/test_migrations.py -q` |
| Job wiring | unit | `JOBS` order | `services/core/tests/test_run_due.py` | `uv run pytest tests/test_run_due.py -q` |
| Docs | none | - | - | build gate only |

## Gate Check Commands

> All run from `services/core`.

| Gate Level | When to Use | Command |
| --- | --- | --- |
| Quick | Unit-only tasks | `uv run pytest tests/<task test file> -q` |
| Full | Integration tasks | `uv run pytest -q` |
| Build | Last task of a phase, or tasks with no tests | `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest -q` |

---

## Execution Plan

### Phase 1: Backtest

```
T1 → T2 → T3 → T4
```

### Phase 2: Weekly record

```
T5 → T6 → T7 → T8
```

---

## Task Breakdown

### T1: Expose the labeller to other modules

**What**: `bank_sync.service.label_transactions` and the `LabelItem` re-export, wrapping `labels.label_all`
**Where**: `services/core/app/modules/bank_sync/service.py`
**Depends on**: None
**Reuses**: `labels.label_all`; the `is_business_day` wrapper pattern
**Requirement**: ACC-03

**Tools**: MCP: NONE. Skill: NONE

**Done when**:

- [x] Returns `(label, linked_id)` per item, equal to `label_all` on the same input, including `in_transit` depending on `today`
- [x] Gate check passes: `uv run pytest tests/test_transaction_labels.py -q`

**Tests**: unit
**Gate**: quick

---

### T2: Replay core

**What**: `origins`, `inputs_at`, `actual_balance`, `replay` and `HorizonScore` in the backtest module
**Where**: `services/core/app/modules/forecasting/backtest.py`
**Depends on**: T1
**Reuses**: `harbor_street.generate`, `detection.detect`, `engine.week_starts`, `strategies.STRATEGIES`
**Requirement**: ACC-03, ACC-04, ACC-05, ACC-06, ACC-07

**Tools**: MCP: NONE. Skill: NONE

**Done when**:

- [x] `inputs_at` has no transaction after `today`, and its balances equal the reference minus later transactions (cash and card)
- [x] `actual_balance` equals the reference minus cash transactions after the Sunday
- [x] Error percent per ACC-05; a zero actual is counted in `zero_actual` and left out of the mean
- [x] Two replays are equal; a history shorter than the warm-up gives 0 origins without raising
- [x] Gate check passes: `uv run pytest tests/test_forecast_backtest.py -q`

**Tests**: unit
**Gate**: quick

---

### T3: Backtest command

**What**: `render` and `main` with `--seed`, and `python -m` entry
**Where**: `services/core/app/modules/forecasting/backtest.py`
**Depends on**: T2
**Reuses**: argparse pattern of `app/fixtures/load.py`
**Requirement**: ACC-01, ACC-02, ACC-08

**Tools**: MCP: NONE. Skill: NONE

**Done when**:

- [x] No arguments: seeds 0–4 × every registered strategy × horizons 1, 4, 13 with mean %, mean $, worst %, origins and zero-actual counts
- [x] `--seed 3` prints only seed 3; `--seed -1` and `--seed x` exit 2 with usage
- [x] `uv run python -m app.modules.forecasting.backtest --seed 0` runs from `services/core`
- [x] Gate check passes: `uv run pytest tests/test_forecast_backtest.py -q`

**Tests**: unit
**Gate**: quick

---

### T4: Record the measured baseline

**What**: A "Measured accuracy" section in the spec 22 file with the horizon-4 means per strategy and seed; Done-when 1 left unticked with a pointer to context.md D5; status In progress
**Where**: `context/specs/22-forecast-accuracy.md`
**Depends on**: T3
**Reuses**: The T3 command output
**Requirement**: ACC-09

**Tools**: MCP: NONE. Skill: NONE

**Done when**:

- [ ] Table matches a fresh run of the command
- [ ] Build gate passes

**Tests**: none
**Gate**: build

---

### T5: Pin and accuracy tables

**What**: `ForecastPin`, `ForecastAccuracy` models and their autogenerated migration (read and corrected)
**Where**: `services/core/app/modules/forecasting/models.py`
**Depends on**: None
**Reuses**: `ForecastSnapshot` conventions, AD-003 naming
**Requirement**: ACC-13, ACC-16

**Tools**: MCP: NONE. Skill: NONE

**Done when**:

- [ ] Migration created with `uv run alembic revision --autogenerate`, then read; it upgrades and downgrades cleanly
- [ ] `ck_forecast_accuracy_horizon` rejects horizon 2
- [ ] Gate check passes: `uv run pytest -q`

**Tests**: integration
**Gate**: full

---

### T6: Weekly pin and error recording

**What**: `record_forecast_accuracy(now)` with its repository queries
**Where**: `services/core/app/modules/forecasting/service.py`
**Depends on**: T5
**Reuses**: `latest_snapshot`, `snapshot_weeks`, `business_time_zones`, `list_connections`, `all_transactions`, `on_conflict_do_nothing`
**Requirement**: ACC-11, ACC-12, ACC-13, ACC-14, ACC-15, ACC-16, ACC-17, ACC-18

**Tools**: MCP: NONE. Skill: NONE

**Done when**:

- [ ] Monday pin; no snapshot means no pin; the Tuesday-after rule; a row equal to forecast − reconstructed actual; skip when the week is missing; rerun is a no-op; one failing business is isolated and logged without amounts; counts returned
- [ ] Edge cases: null balance counts as 0; accounts included at record time; time-zone Monday; no back-dated pins
- [ ] Gate check passes: `uv run pytest -q`

**Tests**: integration
**Gate**: full

---

### T7: Register the job

**What**: `app/jobs/forecast_accuracy.py` and `JOBS = (nightly_bank_sync, forecast_accuracy)`
**Where**: `services/core/app/jobs/__init__.py`
**Depends on**: T6
**Reuses**: `app/jobs/nightly.py`
**Requirement**: ACC-11

**Tools**: MCP: NONE. Skill: NONE

**Done when**:

- [ ] A test asserts `JOBS` is exactly the two jobs in that order
- [ ] Gate check passes: `uv run pytest tests/test_run_due.py -q`

**Tests**: unit
**Gate**: quick

---

### T8: Accuracy history for spec 32

**What**: `AccuracyRecord` and `accuracy_history(session, *, horizon, since)`
**Where**: `services/core/app/modules/forecasting/service.py`
**Depends on**: T7
**Reuses**: repository query pattern
**Requirement**: ACC-19, ACC-20, ACC-21

**Tools**: MCP: NONE. Skill: NONE

**Done when**:

- [ ] Filters by horizon and `since`; orders by week, then business; `error_percent` is derived and null at zero actual
- [ ] `ValueError` for horizon 2; no `/v1` route mentions accuracy
- [ ] Build gate passes

**Tests**: integration
**Gate**: build

---

## Phase Execution Map

```
Phase 1 → Phase 2

Phase 1:  T1 ------→ T2 ------→ T3 ------→ T4
Phase 2:  T5 ------→ T6 ------→ T7 ------→ T8
```
