# 23a - Realign the sample with its reference future

## Problem

Harbor Street's history puts each month's client payments and supplier bills on random days, in random amounts. The engine can't date that money, so it spreads it evenly over the weeks. On the sample, the forecast from 2026-09-26 ends the week of Nov 9 at $28,105.69 (seed 0) and $27,362–$29,911 on seeds 1–4. Every mockup shows $3,150. With the mockups' $5,000 minimum, the sample raises **no** alert. Specs 24, 25, 26 and 27 can't prove their mockup numbers (one gap, $1,850 short, fixes landing at $12,750, $17,650 and $5,150) on the data every one of them tests against.

The same randomness keeps the backtest above the ±10% bar that spec 22 carried to spec 24. The 4-week mean error is 22.55%, 21.56%, 21.02%, 21.73% and 19.68% on seeds 0–4 (spec 22, Measured accuracy). Even a forecast that knew each month's true totals, but not the days, would miss by 14–18%.

When this ships, the default strategy forecasts the alert mockup's gap from the sample's own history. The backtest gates at 10%, and specs 24–27 test against the mockup numbers. The only code that changes is the sample's generator. The engine isn't touched.

## Flow

This reuses the generator's existing skeleton (payroll, rent, software, card, transfers, balances, expected payments) and the existing engine, detection and backtest unchanged. It replaces only the function that writes client payments and supplier bills, and the future's client receipts.

`single module - app/fixtures/harbor_street.py (exists)`; its readers `app.fixtures.load`, `app.modules.forecasting.backtest` and the tests (all exist) are unchanged.

## Impact

| Front | What changes |
| --- | --- |
| domain | sample client payments: they were 6–9 a month on random days from random clients. Now each of 6 clients pays once a month on a fixed day, and Delta Property Management also pays a quarterly contract. Detection (spec 19) now finds them as recurring patterns. `tests/test_recurring_sample.py` branches on this: `test_exactly_three` becomes exactly 10 |
| domain | sample supplier bills: they were 1–3 a month at $800–$4,500. Now there are 2 a month at $800–$2,200 (door 1a), still on random days, so they stay in the forecast's estimate |
| domain | the reference `future`: `FUTURE_CLIENT_RECEIPTS` (Wednesday lump sums) is replaced by the clients' days and base amounts, plus a weekly typical supplier spend from Oct 12. Its card payments after October become -230966 (Nov 9) and -140000 (Dec 8) so the future keeps C14 exactly. C13–C18 keep every value they assert today (opening $42,300, Nov 9 $3,150, others ≥ $17,650, C15, C16, the 3 fixes, payroll dates). `tests/test_forecast_sample.py::test_named_items` skips the reference "Client payments" items and counts 17 checked items, so it changes with this |
| domain | `forecast/status` on a loaded sample: `recurring_count` goes from 3 to 10, and `recurring_names` (largest first) becomes "Delta Property Management", "Payroll". No e2e test reads a loaded sample (the onboarding e2e uses the Plaid sandbox) |
| domain | spec 22's "Measured accuracy" table and spec 24's carried-over Done-when 4 are updated with the new numbers |
| stored data | nothing to migrate. Sample data exists only in local databases (AD-069 refuses any other host); a reload picks up the new history |

## Relations

`None - no stored-data shape change`

## Surface

`None - nothing consumed outside`; the backtest command keeps its flags and output format.

## Landing

| One-way door | Literal shape | Alternative rejected |
| --- | --- | --- |
| 1. The sample's design, which specs 24–27 test against (extends AD-068) | `MONTHLY_CLIENTS = (("Acme Co", 16, 519_997), ("Northgate Dental", 18, 410_000), ("Pine Ridge Homes", 19, 645_277), ("Fairview Condos", 21, 480_000), ("Birch & Co", 23, 560_000), ("Delta Property Management", 24, 430_000))`: day of month (`monthly_day`, next business day), base cents. Each payment is `round(base * rng.uniform(0.98, 1.02))`. `QUARTERLY_CLIENT = ("Delta Property Management", 2, 1_300_000)` in March, June, September and December. Supplier: exactly 2 Coastal Supply Co bills a month, `rng.randint(180_000, 320_000)` on random business days. The odd cents of Acme and Pine Ridge are the seed-0 calibration | A new or changed strategy that dates random income: no method can date money the history puts on random days (spec 22 D5's 14–18% floor), and spec 22 D2 / AGENTS.md want strategy changes to be their own backtested work. Weekly client patterns: a weekly client lands in the next 14 days and breaks spec 18 C16 / spec 21 C40. A quarterly contract in November: its $13,000 would become the largest payment the week after the gap, and the mockup names Birch & Co there. Keeping 3 patterns: a flat estimate can't give $3,150 in the gap week and ≥ $17,650 elsewhere (context.md, Findings) |
| 2. The 10% bar as a gate | `tests/test_forecast_backtest.py` asserts that `replay(generate(seed))["recurring_pattern"][4].mean_percent <= 10.0` for each seed 0–4 | Measuring only (spec 22 D5): superseded by spec 24 D1, which the user decided on 2026-10-09 |

| 1a. Built values for door 1 (added while building, 2026-10-09; door 1's other shapes stand) | `MONTHLY_CLIENTS` bases Acme 486_000, Northgate 383_000, Pine Ridge 604_966 (the seed-0 calibration), Fairview 448_000, Birch 523_000, Delta 402_000; `SUPPLIER_BILL_CENTS = (80_000, 220_000)`; future `TYPICAL_SUPPLIER_CENTS = -129_600` from 2026-10-12, `FUTURE_CARD_PAYMENTS` (2026-11-09, -230_966) and (2026-12-08, -140_000) | The spike's values (Acme 519_997, Pine Ridge 645_277, bills $1,800–$3,200). The real generator draws the random numbers in a different order, and calibrating Pine Ridge alone to $7,705.98 made the business gain $1,250 a month. History balances were then lower, and the backtest rose to 10.4–13.9%. Lowering supplier bills and client income together keeps the drift and gives 6.79–8.56% |

- To record in `.specs/STATE.md` when the checks are approved: door 1 as AD-093 (extends AD-068), door 2 as AD-094 (supersedes spec 22 D5's "measure only").
- Nothing else here is hard to reverse.

## Criteria

### S1: The default forecast of the sample shows the alert mockup's gap (P1)

From the sample's own history, the `recurring_pattern` strategy forecasts the Nov 9 gap and nothing below the fixes' floor.

**Acceptance Criteria**

1. WHEN `recurring_pattern` forecasts `generate(0)` as known on 2026-09-26 (backtest `inputs_at`, plus the 4 expected payments as open occurrences) THEN the week starting 2026-11-09 SHALL end at exactly 315000 cents.
2. WHEN the same forecast runs THEN each of the other 12 weeks SHALL end at 1765000 cents or more.
3. WHEN the same forecast runs for seeds 1, 2, 3 and 4 THEN the week starting 2026-11-09 SHALL end below 500000 cents.
4. WHEN the same forecast runs for seed 0 THEN its non-estimate outgoing items dated 2026-11-09..2026-11-15 SHALL include Coastal Supply Co -1450000 on 2026-11-12 and Payroll -1120000 on 2026-11-13, and its largest incoming item dated 2026-11-16..2026-11-22 SHALL be "Birch & Co, invoice 1057" +960000 on 2026-11-17.
5. The system SHALL keep the next 14 days of the loaded sample at exactly the 4 items of spec 21 C40 (Payroll, "Acme Co, invoice 1042", Software subscriptions, Business Visa), in the same order and amounts.
6. The system SHALL keep the sample's account balances exactly as they are today (`opening_cents` 4230000; spec 18 C4).

**Independent test:** pytest over the pure forecast of `generate(seed)` at 2026-09-26, with no database. Then the existing C40 test against a loaded sample.

### S2: The backtest meets the 10% bar (P1)

**Acceptance Criteria**

7. WHEN `uv run python -m app.modules.forecasting.backtest` runs THEN the `recurring_pattern` 4-week `mean %` SHALL be at most 10.00 on each of seeds 0–4.

**Independent test:** run the command. The gate test asserts the same numbers through `replay`.

### S3: The sample keeps its own guarantees (P1)

**Acceptance Criteria**

8. WHEN detection runs on the sample for each seed 0–9 THEN it SHALL find exactly 10 patterns, with `counterparty` exactly "Payroll", "Wharfside Properties", "Fieldworks Software", "Acme Co", "Northgate Dental", "Pine Ridge Homes", "Fairview Condos", "Birch & Co", and "Delta Property Management" twice (monthly and quarterly).
9. The system SHALL keep every spec 18 check (C1–C18) passing, including C11 (Operating and Reserve ≥ 0 at every end of day, seeds 0–9) and C2 (seeds 0 and 1 differ in a client payment amount).
10. The `future` SHALL date its client receipts on each monthly client's October, November and December day at its base amount, and the quarterly contract on 2026-12-02. It SHALL add one "Typical supplier bills" item on each Monday from 2026-10-12 to 2026-12-21, one fixed amount chosen so the week of 2026-11-09 ends at 315000, while keeping C13–C18's asserted values. (Amended while deriving the checks: a Monday item on Sep 28 or Oct 5 would break spec 18 C16's exactly 4 items in the next 14 days.)

**Independent test:** `uv run pytest tests/test_fixture_harbor_street.py tests/test_recurring_sample.py tests/test_forecast_sample.py`.

## Out of scope

| Excluded | Why |
| --- | --- |
| Any change to detection, strategies, the engine or `CashFlowForecastService` | Condition 7 of the spike. A strategy change is its own backtested work (AGENTS.md) |
| Matching the step 5 mockup's "Payroll, rent, and 9 others" | That copy is illustrative. The sample has 10 patterns and the rule (AD-090) names the largest first, so it reads "Delta Property Management, Payroll, and 8 others" |
| Cash gap alerts | Spec 24 |

## Assumptions

| Assumption | Chosen default | Rationale | Confirmed? |
| --- | --- | --- | --- |
| Changing spec 19 C17 from exactly 3 patterns to exactly 10 (spike condition 6) | Change it, with spec 19's Done-when untouched (it says the sample's payroll, rent and software are found, and they still are) | Dated client payments are the only route the spike found to the mockup's gap and the 10% bar | y (approved, 2026-10-09) |
| Feature name and order | `23a-forecast-sample-realignment`, built before spec 24 (D1) | it amends spec 18 and carries spec 22's bar, and must land between 23 and 24 | y (approved, 2026-10-09) |
| The seed-0 calibration in odd cents (Acme 519,997, Pine Ridge 645,277; as built, only Pine Ridge 604,966 - see Landing 1a) | Keep them as literal constants with a comment | A round number misses $3,150 by cents. Any later change to detection or strategies moves it, and AC 1 fails loudly | y (approved, 2026-10-09) |
| The future's supplier line (AC 10) | One weekly "Typical supplier bills" item, the same amount every Monday | The future is seed-independent (C2), and the engine's supplier estimate is weekly | y (approved, 2026-10-09) |

**Open questions:** none - all resolved or logged above. Ten patterns approved by the user on 2026-10-09.

## Observable

| Surface | Decision | Landing |
| --- | --- | --- |
| command `python -m app.modules.forecasting.backtest` | output format, flags, exit codes | existing - spec 22 (AD-083), unchanged |
| command `python -m app.modules.forecasting.backtest` | what it prints when it fails halfway | existing - spec 22, unchanged |
| command `python -m app.fixtures.load` | output, flags, exit codes | existing - spec 18 (AD-069), unchanged |

## Sources

- `.specs/features/24-alerts-cash-gaps/context.md` - D1 (this feature comes first), the spike's 7 conditions, and its result.
- `design/mockups/alert.dc.html` - $5,000 minimum, $3,150 in the week of Nov 9, $1,850 short, fixes at $12,750, $17,650 and $5,150.
- `context/specs/22-forecast-accuracy.md` - Measured accuracy, and the carried ±10% bar.
