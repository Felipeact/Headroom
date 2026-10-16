from typing import cast

import sentry_sdk
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.types import Event, Hint

from app import problems
from app.log import redact
from app.settings import Settings


def _before_send(event: Event, hint: Hint) -> Event:
    # A structlog line arrives with its whole event dict as the message; Sentry groups by
    # message, so the event name becomes the message and the fields go to `extra`.
    record = hint.get("log_record")
    if record is not None and isinstance(record.msg, dict):
        fields = {k: v for k, v in record.msg.items() if not k.startswith("_")}
        name = str(fields.pop("event", record.name))
        event["logentry"] = {"message": name, "formatted": name, "params": []}
        event["extra"] = {**event.get("extra", {}), **fields}
    return cast(Event, redact(event))


def init_sentry(settings: Settings) -> bool:
    """Start Sentry when SENTRY_DSN is set; return whether it started."""
    if not settings.sentry_dsn:
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        send_default_pii=False,
        before_send=_before_send,
    )
    # The exception itself is reported; its error log line would be a duplicate event.
    ignore_logger(problems.__name__)
    return True
