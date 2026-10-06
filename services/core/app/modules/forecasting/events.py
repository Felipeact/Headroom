"""Events the forecasting module publishes or handles.

It handles `transactions.synced` (AD-048) with `service.refresh_recurring_patterns`
(AD-071), then `service.match_expected_payments` (AD-074), both subscribed in
`app.subscriptions`. It publishes `forecast_inputs.changed` (AD-076).
"""

# After a committed change to something the forecast reads (AD-076). Payload: `source`
# (str, "expected_payments") and the changed input's ID (`expected_payment_id`, str).
FORECAST_INPUTS_CHANGED = "forecast_inputs.changed"
