"""Events the alerts module publishes or handles (spec 24).

It handles `forecast.updated` (AD-079) and `forecast_inputs.changed` with source
`minimum_balance` (AD-089) with `service.check_cash_gaps`, subscribed in
`app.subscriptions` (AD-098). It publishes the three events below after its commit, each
with payload `alert_id` (str) only: event payloads reach logs (AD-097).
"""

# A new cash gap became an open alert.
ALERT_CREATED = "alert.created"
# An alert's shortfall grew by more than 20% or $1,000 since it was last announced or
# dismissed; a dismissed alert is open again.
ALERT_UPDATED = "alert.updated"
# An alert's gap left the forecast.
ALERT_RESOLVED = "alert.resolved"
