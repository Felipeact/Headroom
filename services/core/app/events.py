"""The in-process event bus (spec 14, AD-047).

Modules tell each other that something happened by publishing an `Event` after their own
commit; the modules that care subscribe a handler. Payload values are JSON scalars, so a
message queue can carry the same events unchanged when a module becomes its own service.
"""

import uuid
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Event:
    # `noun.past_tense_verb`, such as `transactions.synced`.
    name: str
    business_id: uuid.UUID
    payload: Mapping[str, str | int | bool]


Handler = Callable[[Event], None]

_handlers: defaultdict[str, list[Handler]] = defaultdict(list)


def subscribe(name: str, handler: Handler) -> None:
    """Call `handler` with every event published under `name`, after earlier subscribers."""
    _handlers[name].append(handler)


def unsubscribe(name: str, handler: Handler) -> None:
    """Stop calling `handler` for `name`; does nothing if it was not subscribed."""
    if handler in _handlers[name]:
        _handlers[name].remove(handler)


def publish(event: Event) -> None:
    """Call every handler subscribed to `event.name`, in order. Call it after committing.

    A handler that raises is logged and skipped; the others still run, and the publisher
    never sees the error, because its data is already committed.
    """
    for handler in list(_handlers[event.name]):
        try:
            handler(event)
        except Exception as exc:  # noqa: BLE001 - one failing subscriber must not stop the rest
            log.error(
                "event.handler_failed",
                event_name=event.name,
                handler=getattr(handler, "__qualname__", repr(handler)),
                error_type=type(exc).__name__,
            )
