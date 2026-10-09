# 23a - Realign the sample with its reference future checks

Profile: light
Plan: `.specs/features/23a-forecast-sample-realignment/plan.md`

12 checks in 3 slices · 2 one-way doors · 0 open

All proofs run from `services/core`.

## Checks

### S1 - The default forecast of the sample shows the alert mockup's gap · 3 files · 44 KB · ~11k

**C1** - `recurring_pattern` over `generate(0)` as known on 2026-09-26 (`backtest.inputs_at` plus the 4 expected payments as open occurrences) ends the week starting 2026-11-09 at exactly 315000 (AC 1, door 1)
Proof: `uv run pytest tests/test_sample_realignment.py -k test_gap_week_seed_0`

**C2** - In the same forecast, each of the other 12 weeks ends at 1765000 or more (AC 2)
Proof: `uv run pytest tests/test_sample_realignment.py -k test_other_weeks_seed_0`

**C3** - For seeds 1, 2, 3 and 4, the same forecast ends the week of 2026-11-09 below 500000 (AC 3)
Proof: `uv run pytest tests/test_sample_realignment.py -k test_gap_week_other_seeds`

**C4** - Seed 0's non-estimate outgoing items dated 2026-11-09..2026-11-15 include (2026-11-12, -1450000, "Coastal Supply Co, quarterly order") and (2026-11-13, -1120000, payroll). Its largest non-estimate incoming item dated 2026-11-16..2026-11-22 is (2026-11-17, +960000, "Birch & Co, invoice 1057") (AC 4)
Proof: `uv run pytest tests/test_sample_realignment.py -k test_gap_week_items`

**C5** - A loaded sample's `GET .../upcoming?days=14` still returns exactly the 4 items of spec 21 C40 (AC 5)
Proof: `uv run pytest tests/test_forecast_sample.py -k test_upcoming_next_14_days`

**C6** - Account balances are unchanged: Operating 800000, Reserve 3430000, line of credit 0 (available 2000000), Visa owes 245000, and `future.opening_cents` 4230000 (AC 6)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "test_banks_and_accounts or test_future_weeks_add_up"`

### S2 - The backtest meets the 10% bar · 2 files · 18 KB · ~5k

**C7** - For each seed 0–4, `backtest.replay(generate(seed))["recurring_pattern"][4].mean_percent` is at most 10.0 (AC 7, door 2)
Proof: `uv run pytest tests/test_forecast_backtest.py -k test_ten_percent_bar`
Proof: `uv run python -m app.modules.forecasting.backtest` (the 4-week `recurring_pattern` rows, read by hand, ≤ 10.00)

### S3 - The sample keeps its own guarantees · 4 files · 60 KB · ~15k

**C8** - For each seed 0–9, a loaded sample's `GET .../recurring-patterns` returns exactly 10 patterns, whose sorted `counterparty` values are "Acme Co", "Birch & Co", "Delta Property Management" ×2, "Fairview Condos", "Fieldworks Software", "Northgate Dental", "Payroll", "Pine Ridge Homes" and "Wharfside Properties". Delta's two schedules are `monthly` and `quarterly` (AC 8; replaces spec 19 C17 by user approval, 2026-10-09)
Proof: `uv run pytest tests/test_recurring_sample.py -k test_exactly_ten`

**C9** - Every spec 18 history check still passes: C1 same seed identical, C2 seeds differ in a client amount, C5 span and types, C6 payroll, C7 rent and software, C8 suppliers and clients, C9 card pairs, C10 transfers, and C11 balances ≥ 0 on seeds 0–9 (AC 9)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "test_same_seed_identical or test_seeds_differ_only_in_history or test_history_span_and_types or test_payroll_schedule or test_monthly_rent_and_software or test_suppliers_and_clients or test_card_payments_pair or test_monthly_transfers or test_balances_never_negative"`

**C10** - The future dates each monthly client's receipt ("Payment from <client>") on its day of October, November and December (by `monthly_day`, between 2026-09-27 and 2026-12-27) at its base amount. It dates Delta's quarterly receipt on 2026-12-02 at 1300000, and has exactly one "Typical supplier bills" item on each of the 11 Mondays 2026-10-12..2026-12-21, all the same negative amount (AC 10)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k test_future_client_receipts`

**C11** - The future keeps spec 18 C13–C18: the week ends add up, Nov 9 = 315000 and the others ≥ 1765000, the 3 causes, the 4 items in the next 14 days, the 3 fixes (1275000, 1765000, 515000), and the payroll, rent and software dates (AC 10)
Proof: `uv run pytest tests/test_fixture_harbor_street.py -k "test_future_weeks_add_up or test_future_gap_week_of_nov_9 or test_future_gap_causes or test_future_next_14_days or test_future_three_fixes or test_future_continues_history or test_future_expected_payments"`

**C12** - Spec 21 C23 on the new sample: the loaded forecast's non-estimate, non-card items are exactly payroll ×6, rent ×3, software ×3, the 4 expected payments, the monthly clients' receipts in the window, and Delta's quarterly on 2026-12-02, each client item carrying its `counterparty` and a `schedule` of `monthly` or `quarterly` (Impact row 3)
Proof: `uv run pytest tests/test_forecast_sample.py -k test_named_items`

**C13** - Every AGENTS.md API check passes: `ruff format --check`, `ruff check`, `mypy app`, full `pytest`
Proof: `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest`

## Coverage

| Set (size) | Member -> proof | Unproven |
| --- | --- | --- |
| spike conditions (7) | 1 gap & others C1, C2 · 2 other seeds C3 · 3 next 14 days C5 · 4 backtest C7 · 5 balances C6 · 6 patterns C8 · 7 no engine edit C13 (diff touches no `app/modules/forecasting` file, read by the Verifier) | - |
| seeds for the 10% bar (5) | 0 C7 · 1 C7 · 2 C7 · 3 C7 · 4 C7, parametrized | - |
| seeds below $5,000 (4) | 1 C3 · 2 C3 · 3 C3 · 4 C3, parametrized | - |
| sample patterns (10) | Payroll C8 · Wharfside C8 · Fieldworks C8 · Acme C8 · Northgate C8 · Pine Ridge C8 · Fairview C8 · Birch C8 · Delta monthly C8 · Delta quarterly C8 | - |
| future item kinds (7) | payroll C11 · rent C11 · software C11 · card C11 · expected C11 · client receipts C10 · typical supplier C10 | - |
| Landing doors (2) | 1 sample design C1, C8, C10 · 2 the 10% gate C7 | - |

- No check claims a status code. C5, C8 and C12 cross the API through `TestClient` on a loaded sample; C1–C4 and C7 are pure, with no database

## Swept

- validation: n/a - no input; the generator takes only a seed, already validated by spec 18 and 22's commands
- failure modes: n/a - the generator is pure and has no partial state
- idempotency: C9 (C1 of spec 18: same seed, identical output)
- authorization: n/a - no route added
- concurrency: n/a - pure function, no shared state
- data lifecycle: n/a - nothing stored outside local sample loads, which AD-069 already gates
- dependency failure: n/a - no external dependency
- state transitions: n/a - no state
- observability: C7 (the backtest command prints the accuracy that gates)

## Handoff

- S1–S3 ≈ 31k (harbor_street.py 22 KB, 5 test files ~100 KB read in part), well under the 150k budget - one builder
