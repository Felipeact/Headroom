# Spec 21: The 13-week forecast

- **Milestone:** 4, forecast
- **Status:** Not started
- **Depends on:** 19, 20

## Goal

Project the business's cash balance week by week for the next 13 weeks.

## Build

- Start from the balances of the included accounts, then apply the predicted and expected payments.
- Weeks start on Monday, in the business's time zone. Each of the 13 weeks has:
  - the projected end-of-week balance
  - total money in and total money out
  - a low and a high estimate
  - the IDs of the payments behind the totals
- Every forecast item records its account.
- Forecasting methods sit behind `ForecastStrategy`. `recurring_pattern` is the default and `rolling_average` is the fallback. Both always return 13 weeks and never fail on empty history.
- Recalculate on `transactions.synced` or `forecast_inputs.changed`. Save each result as a snapshot keyed by business and sync ID, then publish `forecast.updated`.
- Mark the forecast as incomplete when an included connection needs attention or hasn't synced for 48 hours.
- `GET /v1/businesses/{business_id}/forecast` and `GET /v1/businesses/{business_id}/upcoming?days=14`.

## Done when

- [ ] The forecast returns 13 weeks for a business with no history, with 2 weeks of history, and with 2 years of history.
- [ ] Processing the same event twice produces only one snapshot.
- [ ] A forecast for 2 years of history takes under 2 seconds.
