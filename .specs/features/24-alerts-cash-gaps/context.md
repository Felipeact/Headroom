# Spec 24 context: user decisions

Decided 2026-10-09, before the plan was written.

| # | Gray area | Decision |
| --- | --- | --- |
| D1 | Where the sample recalibration and the carried-over ±10% bar go (spec 21 plan "Spec 24 recalibrates the sample"; spec 22 D5-D7) | A separate feature, built **before** spec 24: realign Harbor Street so the engine forecasts the alert mockup's gap, and gate the backtest at ±10%. Spec 24 then proves its alert against the real mockup numbers ($5,000 minimum, $3,150 low, short by $1,850). |
| D2 | A dismissed alert whose gap grows by more than 20% or $1,000 | It reopens (state `open`) and publishes `alert.updated`, so spec 29 emails it. A dismissal silences the gap at its current size, not a worse one. |

## Findings (2026-10-09)

- `forecast_weeks.low_cents` / `high_cents` are the uncertainty band (`strategies.py:438`), not an intra-week minimum. A cash gap is judged on `end_balance_cents`, which matches the glossary and the mockup's $3,150 (the reference week end).
- Engine output on the sample today (`recurring_pattern`, from 2026-09-26, expected payments included): the lowest week end is the week of Nov 9 at $28,106 (seed 0), and $27,362-$29,911 on seeds 1-4. With a $5,000 minimum the sample raises **no** alert.
- A flat weekly estimate can't produce the mockup's shape at the current $42,300 opening. The Nov 9 week at $3,150 needs about +$3,200/week net estimate, and every other week at or above $17,650 (spec 25's fixes) needs at least +$9,300/week.

## Spike before the realignment plan

The realignment is an open bet, so a time-boxed probe in the scratchpad comes first (no repo changes). It reports which of these hold together on one sample design:

1. Seed 0 forecast: the week of Nov 9 ends at $3,150, and every other week at $17,650 or more. Moving Birch & Co to Nov 10, moving Coastal Supply Co to Nov 19, or drawing $2,000 gives lowest balances of $12,750, $17,650 and $5,150 (spec 25).
2. Seeds 1-4: the week of Nov 9 ends below $5,000.
3. The next 14 days still hold exactly the 4 items of spec 18 C16 / spec 21 C40 and the dashboard mockup.
4. Backtest 4-week mean error at most 10% on seeds 0-4.
5. Opening balances unchanged (dashboard mockup).
6. Recurring patterns exactly 3 on seeds 0-9 (spec 19 C17). If regular client payments are the route, this check has to change, and that needs the user's approval.
7. No edit to `CashFlowForecastService`. A strategy change is a new or changed strategy class, with the backtest before and after (spec 22 D2, AGENTS.md).

Candidate route: client payments on fixed days of the month (16th-26th), so spec 19 detects them as patterns, the forecast dates them, the week of Nov 9 has none, and the backtest error falls.

## Spike result (2026-10-09)

Scratchpad only; no repo file changed. One design holds all 7 conditions together ("design B"):

- **Clients:** 6 clients each pay once a month on a fixed day, with ±2% noise per payment from the seed: Acme Co on the 16th ($5,199.97), Northgate Dental on the 18th ($4,100), Pine Ridge Homes on the 19th ($6,452.77), Fairview Condos on the 21st ($4,800), Birch & Co on the 23rd ($5,600), and Delta Property Management on the 24th ($4,300). Delta also pays a quarterly contract on the 2nd of Mar/Jun/Sep/Dec ($13,000). Acme's and Pine Ridge's odd cents are the calibration that puts seed 0 exactly on $3,150.
- **Supplier:** 2 Coastal Supply Co bills a month on random business days, $1,800 to $3,200 each (today 1 to 3 bills, $800 to $4,500).
- Everything else is unchanged: payroll, rent, software, card, transfers, balances and expected payments.

| # | Condition | Result |
| --- | --- | --- |
| 1 | Seed 0: Nov 9 week = $3,150, the others ≥ $17,650 | holds: $3,150.00; lowest other week $19,049.91 (Dec 7). The 3 fixes give $12,750, $17,650 and $5,150 |
| 2 | Seeds 1–4: Nov 9 week < $5,000 | holds: $1,657.72, $3,407.54, $2,239.39, $2,938.88 (from the run before the 1-cent calibration) |
| 3 | Next 14 days = the 4 items | holds on seeds 0–4 |
| 4 | Backtest 4-week mean ≤ 10% | holds: 8.25, 8.88, 9.42, 7.15, 8.96 (seeds 0–4) |
| 5 | Opening balances unchanged | holds: $42,300 |
| 6 | Exactly 3 patterns | **changes**: exactly 10 on seeds 0–9 (the 3, plus 6 monthly clients and Delta's quarterly). Needs approval |
| 7 | No edit to `CashFlowForecastService` or the strategies | holds: only `harbor_street.py` changes |

Also checked: spec 18 C11 holds on seeds 0–9 (Operating's lowest end of day is ≥ $3,000.52, Reserve's is ≥ $10,785.38). On seed 0 the gap week's outgoing named items are Visa -$2,844.89 (Nov 9), Software -$640 (Nov 9), Coastal -$14,500 (Nov 12) and Payroll -$11,200 (Nov 13). The named items arriving the week after are Acme +$5,144.68 (Nov 16), Birch +$9,600 (Nov 17), Northgate +$4,093.44 (Nov 18) and Pine Ridge +$6,473.92 (Nov 19).

Why fixed days 16–25 only: a monthly client on the 1st–9th would land in the next 14 days (condition 3), one on the 10th–15th would land in the Nov 9 week, and Sep 26–30 sits after the reference day. With only those days, the 4 weeks after the gap need about $15,000 more income than the 7 weeks before it. The quarterly contract on Dec 2 supplies it. On the 2nd it stays out of the week after the gap, so Birch & Co is the largest payment arriving then, as in the mockup.

Rejected routes: weekly client patterns (one would land in the next 14 days); a flat estimate (can't make this shape, see Findings); quarterly in Nov (its $13,000 would be the largest payment the week after the gap, not Birch & Co).
