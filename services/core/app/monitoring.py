from typing import cast

import sentry_sdk
from sentry_sdk.integrations.logging import ignore_logger
from sentry_sdk.types import Event, Hint

from app import problems
from app.log import redact
from app.settings import Settings


def _before_send(event: Event, hint: Hint) -> Event:
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
