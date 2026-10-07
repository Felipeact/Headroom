# Spec 22 context: user decisions

Decided 2026-10-07, before the spec was written.

| # | Gray area | Decision |
| --- | --- | --- |
| D1 | How "the 4-week forecast is within ±10%" is judged | Mean absolute percentage error over every replayed week at the 4-week horizon is at most 10%. The worst week is reported, not gated. |
| D2 | What happens if the current strategy misses the bar | Tune it inside spec 22: a new or changed strategy class, never `CashFlowForecastService`, with the backtest before and after in the commit message. |
| D3 | Which stored forecast counts as "made N weeks ago" | A weekly job pins the snapshot that is current at the start of each business-local week; errors are computed from the pinned snapshot only. Snapshots are reused when inputs revert (AD-077), so the history cannot be rebuilt afterwards. |
| D4 | Which sample seeds must meet the bar | Seeds 0, 1, 2, 3 and 4, each on its own. `--seed` runs a single one. |
| D5 | The 10% bar can't be met honestly (found 2026-10-07 by prototype) | Measure only. The replay's best possible 4-week error is 14–18%, because the sample puts client payments and supplier bills on random days. The reference future is 48% off at week 4, because it assumes less income than the history shows. Spec 22 builds the measurement and leaves Done-when 1 unticked with the numbers. A separate follow-up realigns Harbor Street's history with its reference future (spec 18 amendment), then re-gates at 10%. Supersedes D1, D2 and D4's "must pass". |
| D6 | Spec 21 doesn't reproduce the Nov 9 gap (found by the same probe) | Already known: spec 21's plan (fbfba53, user decision 2026-10-07) pins only the sample's named items, and spec 24 recalibrates the week ends. Spec 22 changes nothing here. The D5 sample realignment should be planned together with spec 24's recalibration. |

## Prototype evidence (2026-10-07)

4-week mean absolute percentage error, 61 origins per seed:

| | Seed 0 | 1 | 2 | 3 | 4 |
| --- | --- | --- | --- | --- | --- |
| `recurring_pattern` | 22.6 | 21.6 | 21.0 | 21.7 | 19.7 |
| `rolling_average` | 21.0 | 20.9 | 22.0 | 20.9 | 18.5 |
| Flat balance | 17.8 | 19.4 | 19.9 | 17.7 | 16.9 |
| Knows true monthly totals, not the days | 14.7 | 16.6 | 18.5 | 13.8 | 15.9 |

Seed 0 forecast from 2026-09-26 vs the reference future: week 4 is $48,141 vs $32,510 (48%), and the week of Nov 9 is $28,105 vs $3,150.
