"""Events the forecasting module publishes or handles.

It handles `transactions.synced` (AD-048) with `service.refresh_recurring_patterns`
(AD-071), then `service.match_expected_payments` (AD-074), then
`service.recompute_forecast` (AD-079), which also handles `forecast_inputs.changed`; all
are subscribed in `app.subscriptions`. It publishes `forecast_inputs.changed` (AD-076)
and `forecast.updated` (AD-079).
"""

# After a committed change to something the forecast reads (AD-076). Payload: `source`
# (str) and the changed input's ID: `expected_payments` with `expected_payment_id`, or
# `bank_accounts` with `account_id` (AD-081).
FORECAST_INPUTS_CHANGED = "forecast_inputs.changed"

# After the commit of a business's new latest forecast snapshot (AD-079). Payload:
# `snapshot_id` (str). Never an amount: event payloads reach logs.
FORECAST_UPDATED = "forecast.updated"
