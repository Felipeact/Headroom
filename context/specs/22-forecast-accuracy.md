# Spec 22: Forecast accuracy

- **Milestone:** 4, forecast
- **Status:** In progress
- **Depends on:** 21

## Goal

Measure how accurate the forecast is, so changes to it can be judged with numbers.

## Build

- `uv run python -m app.modules.forecasting.backtest` replays the sample data. For each past week, it forecasts using only what was known then, and reports the average error at 1, 4, and 13 weeks for each strategy.
- Each week, compare earlier forecasts with the actual balances, and store the error.

## Done when

- [ ] On the sample data, the 4-week forecast is within ±10% of the actual balance. *Not met yet: the current sample can't support it (see Measured accuracy). This waits for the sample to be realigned with its reference future, planned with spec 24.*
- [x] The accuracy history is available for the weekly report in spec 32. *`forecasting.service.accuracy_history`, filled each week by the hourly `forecast_accuracy` job.*

## Measured accuracy

From `uv run python -m app.modules.forecasting.backtest` on 2026-10-07: the mean absolute percentage error at 4 weeks, over 61 replayed weeks per seed.

| Strategy | Seed 0 | Seed 1 | Seed 2 | Seed 3 | Seed 4 |
|---|---|---|---|---|---|
| `recurring_pattern` (default) | 22.55% | 21.56% | 21.02% | 21.73% | 19.68% |
| `rolling_average` | 20.96% | 20.93% | 21.96% | 20.93% | 18.49% |

**Why ±10% isn't reachable on this sample yet:** Harbor Street puts each month's client payments and supplier bills on random days. A forecast that knew every month's true totals, but not the days, would still miss by 14–18% at 4 weeks. A forecast that keeps the balance flat misses by 17–20%. Details and the decision are in `.specs/features/22-forecast-accuracy/context.md` (D5).

