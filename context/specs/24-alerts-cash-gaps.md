# Spec 24: Cash gap alerts

- **Milestone:** 5, alerts and dashboard
- **Status:** In progress
- **Depends on:** 23

## Goal

Find the weeks when cash will drop below the minimum, and explain why.

## Build

- When `forecast.updated` arrives, find every cash gap: one or more weeks in a row below the minimum. For each, record the first week, the lowest balance, and the shortfall.
- **Explanation:** list the large payments going out during the gap or just before it, and the money that arrives only after it. Each item shows its amount, date, and counterparty.
- **States:** open, resolved, or dismissed.
- **Events:**
  - Publish `alert.created` for a new gap.
  - Publish `alert.updated` only when the shortfall grows by more than 20% or $1,000.
  - Never create two alerts for the same gap.
- **API:** `GET` the alerts list, `GET` a single alert, and `POST .../alerts/{alert_id}/dismiss`.

## Done when

- [ ] The sample data's gap in the week of Nov 9 produces one alert, naming the supplier payment and payroll.
- [ ] Processing the same forecast again creates no duplicate, and small changes publish nothing.
- [ ] A gap that disappears from the forecast becomes resolved.
- [x] *Carried over from spec 22:* on seeds 0–4, the default strategy's 4-week mean error in `uv run python -m app.modules.forecasting.backtest` is within ±10%. This needs Harbor Street's history realigned with its reference future (a spec 18 amendment): today, client payments and supplier bills fall on random days, which puts the floor at 14–18%. See spec 22's Measured accuracy. *Done by feature 23a (2026-10-09): 8.56%, 6.79%, 7.22%, 6.92%, 7.50% on seeds 0–4, gated by `tests/test_forecast_backtest.py::test_ten_percent_bar`.*
