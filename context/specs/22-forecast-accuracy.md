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

- [ ] On the sample data, the 4-week forecast is within ±10% of the actual balance.
- [ ] The accuracy history is available for the weekly report in spec 32.
