"""Every event subscription in the application, in one place (spec 15).

Both processes that publish events call `register()`: the API at startup and the hourly
jobs runner. A handler subscribed anywhere else would miss the events published by the
other process. Specs 16, 20 and 21 add their handlers to `SUBSCRIPTIONS`.
"""

from app import events
from app.modules.bank_sync.events import TRANSACTIONS_SYNCED
from app.modules.forecasting import service as forecasting_service

# Order matters: handlers run in this order (AD-047). Recurring patterns come first, so
# a forecast built on the same event reads fresh ones (AD-071); expected payment matches
# come next, for the same reason (AD-074).
SUBSCRIPTIONS: tuple[tuple[str, events.Handler], ...] = (
    (TRANSACTIONS_SYNCED, forecasting_service.refresh_recurring_patterns),
    (TRANSACTIONS_SYNCED, forecasting_service.match_expected_payments),
)

_registered: set[tuple[str, events.Handler]] = set()


def register() -> None:
    """Subscribe every handler in `SUBSCRIPTIONS`; a second call subscribes nothing."""
    for name, handler in SUBSCRIPTIONS:
        if (name, handler) not in _registered:
            events.subscribe(name, handler)
            _registered.add((name, handler))
