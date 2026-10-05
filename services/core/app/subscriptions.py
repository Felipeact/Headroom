"""Every event subscription in the application, in one place (spec 15).

Both processes that publish events call `register()`: the API at startup and the hourly
jobs runner. A handler subscribed anywhere else would miss the events published by the
other process. Specs 16, 20 and 21 add their handlers to `SUBSCRIPTIONS`.
"""

from app import events

SUBSCRIPTIONS: tuple[tuple[str, events.Handler], ...] = ()

_registered: set[tuple[str, events.Handler]] = set()


def register() -> None:
    """Subscribe every handler in `SUBSCRIPTIONS`; a second call subscribes nothing."""
    for name, handler in SUBSCRIPTIONS:
        if (name, handler) not in _registered:
            events.subscribe(name, handler)
            _registered.add((name, handler))
