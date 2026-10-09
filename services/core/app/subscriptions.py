"""Every event subscription in the application, in one place (spec 15).

Both processes that publish events call `register()`: the API at startup and the hourly
jobs runner. A handler subscribed anywhere else would miss the events published by the
other process. Specs 16, 20, 21 and 24 add their handlers to `SUBSCRIPTIONS`.
"""

from app import events
from app.modules.alerts import service as alerts_service
from app.modules.bank_sync.events import TRANSACTIONS_SYNCED
from app.modules.forecasting import service as forecasting_service
from app.modules.forecasting.events import FORECAST_INPUTS_CHANGED, FORECAST_UPDATED

# Order matters: handlers run in this order (AD-047). Recurring patterns come first, so
# a forecast built on the same event reads fresh ones (AD-071); expected payment matches
# come next, for the same reason (AD-074); the forecast reads both (AD-079). Alerts come
# last: a minimum change leaves the forecast unchanged, so they re-check it on the same
# event, after the recompute (AD-098).
SUBSCRIPTIONS: tuple[tuple[str, events.Handler], ...] = (
    (TRANSACTIONS_SYNCED, forecasting_service.refresh_recurring_patterns),
    (TRANSACTIONS_SYNCED, forecasting_service.match_expected_payments),
    (TRANSACTIONS_SYNCED, forecasting_service.recompute_forecast),
    (FORECAST_INPUTS_CHANGED, forecasting_service.recompute_forecast),
    (FORECAST_UPDATED, alerts_service.check_cash_gaps),
    (FORECAST_INPUTS_CHANGED, alerts_service.check_cash_gaps),
)

_registered: set[tuple[str, events.Handler]] = set()


def register() -> None:
    """Subscribe every handler in `SUBSCRIPTIONS`; a second call subscribes nothing."""
    for name, handler in SUBSCRIPTIONS:
        if (name, handler) not in _registered:
            events.subscribe(name, handler)
            _registered.add((name, handler))
