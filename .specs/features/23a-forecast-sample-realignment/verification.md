# 23a - Realign the sample with its reference future verification

**Verdict**: PASS
**Profile**: light
**Diff range**: 1285b43..0ac511fbabc9040ea645f215cbd4eba1f1622e96
**Round**: 1 - full
**Verifier**: independent sub-agent (author != verifier)

## Binding sources

None are marked binding at `light`; for context I opened `.specs/features/24-alerts-cash-gaps/context.md` (D1, spike conditions 1-7), `context/specs/22-forecast-accuracy.md` (Measured accuracy, updated in this diff) and `design/mockups/alert.dc.html` ($5,000, $3,150, $1,850, $12,750, $17,650, $5,150 each present once) - no contradiction with the checks found.

## Checks

All proofs run at HEAD `0ac511f` from `services/core` in one invocation: `uv run pytest tests/test_sample_realignment.py tests/test_fixture_harbor_street.py tests/test_recurring_sample.py tests/test_forecast_sample.py tests/test_forecast_backtest.py -v` - 70 passed, 0 failed; every named test below appears individually as PASSED.

| Check | Claim | Proof run | Evidence | Result |
| --- | --- | --- | --- | --- |
| C1 | seed 0, `recurring_pattern` at 2026-09-26: week of 2026-11-09 ends at exactly 315000 | `test_sample_realignment.py::test_gap_week_seed_0` PASSED | `tests/test_sample_realignment.py:46` - `assert ends(forecast(0))[WEEK_OF_NOV_9] == 315000` | PASS |
| C2 | the other 12 weeks end >= 1765000 | `test_sample_realignment.py::test_other_weeks_seed_0` PASSED | `tests/test_sample_realignment.py:52-53` - `assert len(others) == 12`; `assert all(end >= 1765000 for end in others.values())` | PASS |
| C3 | seeds 1-4: week of Nov 9 < 500000 | `test_gap_week_other_seeds[1..4]` PASSED (4 params) | `tests/test_sample_realignment.py:59` - `assert ends(forecast(seed))[WEEK_OF_NOV_9] < 500000`, parametrized `[1, 2, 3, 4]` at :56 | PASS |
| C4 | Nov 9-15 outgoing includes Coastal -1450000 (11-12) and Payroll -1120000 (11-13); largest Nov 16-22 incoming is Birch +960000 (11-17) | `test_sample_realignment.py::test_gap_week_items` PASSED | `tests/test_sample_realignment.py:70-71` - `assert (date(2026, 11, 12), -1450000, "Coastal Supply Co, quarterly order") in out`, `assert (date(2026, 11, 13), -1120000, "Payroll") in out`; `:78` - `assert (largest.date, largest.amount_cents, largest.description) == (date(2026, 11, 17), 960000, "Birch & Co, invoice 1057")` | PASS |
| C5 | loaded sample `upcoming?days=14` = exactly spec 21 C40's 4 items | `test_forecast_sample.py::test_upcoming_next_14_days` PASSED | `tests/test_forecast_sample.py:124` - `assert [(i["description"], i["amount_cents"], i["date"]) for i in items] == [("Payroll", -1_120_000, "2026-10-02"), ("Acme Co, invoice 1042", 800_000, ...), ("Software subscriptions", -64_000, ...), ("Business Visa", -245_000, ...)]` | PASS |
| C6 | balances unchanged: Operating 800000, Reserve 3430000, LOC 0/2000000, Visa 245000, opening 4230000 | `test_banks_and_accounts`, `test_future_weeks_add_up` PASSED | `tests/test_fixture_harbor_street.py:89` - `assert got == {... 800000 ... 3430000 ... 0, 2000000 ... 245000 ...}`; `:327` - `assert future.opening_cents == 4230000` | PASS |
| C7 | 4-week `recurring_pattern` mean % <= 10.0 on seeds 0-4 | `test_ten_percent_bar[0..4]` PASSED; `uv run python -m app.modules.forecasting.backtest` exit 0, 4-week rows 8.56 / 6.79 / 7.22 / 6.92 / 7.50 | `tests/test_forecast_backtest.py:244` - `assert score.mean_percent <= 10.0` (with `:243` `is not None`), parametrized `[0, 1, 2, 3, 4]` | PASS |
| C8 | seeds 0-9: exactly 10 patterns with the named counterparties; Delta monthly + quarterly | `test_recurring_sample.py::test_exactly_ten[0..9]` PASSED | `tests/test_recurring_sample.py:123` - `assert sorted(p["counterparty"] for p in patterns) == ["Acme Co", "Birch & Co", "Delta Property Management", "Delta Property Management", "Fairview Condos", "Fieldworks Software", "Northgate Dental", "Payroll", "Pine Ridge Homes", "Wharfside Properties"]`; `:140` - `assert delta == ["monthly", "quarterly"]` | PASS |
| C9 | spec 18 history checks C1, C2, C5-C11 still pass (C11 on seeds 0-9) | the 9 named tests PASSED, `test_balances_never_negative[0..9]` | `tests/test_fixture_harbor_street.py:53` - `assert first == second` (C1); `:66` - `assert amounts_a != amounts_b` over `_clients` (C2); `:142` - `assert {t.amount_cents for t in payroll} == {-1120000}` (C6); `:204` - `assert clients >= CLIENTS_KNOWN` (C8); `:257` - `assert balance >= 0, (seed, key, day, balance)` (C11) | PASS |
| C10 | future client receipts on each client's Oct/Nov/Dec `monthly_day` at base, Delta quarterly 2026-12-02 at 1300000, one equal negative "Typical supplier bills" on each of 11 Mondays 2026-10-12..2026-12-21 | `test_fixture_harbor_street.py::test_future_client_receipts` PASSED | `tests/test_fixture_harbor_street.py:461` - `assert receipts == expected` (expected built at :447-460 from `monthly_day(day, (2026, month))`, base, plus `(date(2026, 12, 2), 1_300_000, ...)`); `:463` - `assert [i.date for i in supplier] == [date(2026, 10, 12) + timedelta(weeks=n) for n in range(11)]`; `:466-467` - one amount, `< 0` | PASS |
| C11 | future keeps spec 18 C13-C18 | the 7 named tests PASSED | `tests/test_fixture_harbor_street.py:340-341` - `assert ends[gap] == 315000`, `assert all(end >= 1765000 ...)`; `:365` - `assert len(window) == 4`; `:401` - `assert min(_week_ends(future.opening_cents, edited)) == lowest` over 1275000 / 1765000 / 515000; `:330` - week ends add up | PASS |
| C12 | loaded forecast's named items: payroll x6, rent x3, software x3, 4 expected, monthly client receipts with counterparty + schedule, Delta quarterly on 2026-12-02 | `test_forecast_sample.py::test_named_items` PASSED | `tests/test_forecast_sample.py:84-87` - `assert sorted((i["date"], i["counterparty"], i["schedule"]) for i in clients) == expected_clients` (incl. `("2026-12-02", "Delta Property Management", "quarterly")`); `:60` - `assert named(others) == sorted(...)`; `:118` - `assert checked == 17` | PASS |
| C13 | ruff format, ruff check, mypy, full pytest | `uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest` exit 0 | 120 files already formatted; All checks passed!; mypy no issues in 48 files; 792 passed, 5 deselected (default marker filter) | PASS |

Spike condition 7 (no engine edit): `git diff --name-only 1285b43..HEAD -- services/core/app/modules/` returns nothing; the only app file changed is `services/core/app/fixtures/harbor_street.py`.

Built constants match Landing row `1a`: `app/fixtures/harbor_street.py:48-55` (bases 486_000 / 383_000 / 604_966 / 448_000 / 523_000 / 402_000), `:58` quarterly `("Delta Property Management", 2, 1_300_000)`, `:61-62` 2 bills at `(80_000, 220_000)`, `:225` `FUTURE_CARD_PAYMENTS` (-230_966, -140_000), `:227` `TYPICAL_SUPPLIER_CENTS = -129_600`. The checks follow row 1a and amended AC 10 (supplier line from 2026-10-12, 11 Mondays), so checks and plan agree as the plan now stands.

Level and sampling: C1-C4 and C7 are pure over the generator plus the real strategy, matching the AC wording; C5, C8, C12 cross the API through `TestClient` on a loaded sample. Seed sets are fully parametrized (C3 1-4, C7 0-4, C8 and C9/C11 0-9). No status-code claims. No gaps that fail the feature. Non-blocking notes: (a) plan `Assumptions` row 3 still names the spike's odd cents (Acme 519,997, Pine Ridge 645,277), superseded by row 1a where only Pine Ridge carries the calibration - stale prose only; (b) C12 asserts client item amounts only as `> 0`, which is all the claim states.

Swept rows resolving to existing: idempotency -> C9 (spec 18 C1, `test_fixture_harbor_street.py:53-54` same seed identical, verified present and passing); observability -> C7 (backtest command prints the gating 4-week rows, verified by running it). Other rows are `n/a` policy.

## Gate

`uv run ruff format --check . && uv run ruff check . && uv run mypy app && uv run pytest` (services/core, at 0ac511f) - 792 passed, 0 failed, 5 deselected; exit 0
