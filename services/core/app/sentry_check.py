"""Send one deliberate test error to Sentry: `uv run python -m app.sentry_check`."""

import sys
from datetime import UTC, datetime

import sentry_sdk

from app.monitoring import init_sentry
from app.settings import get_settings

FLUSH_TIMEOUT_SECONDS = 10


class SentryCheckError(Exception):
    pass


def main() -> int:
    if not init_sentry(get_settings()):
        print("SENTRY_DSN is not set", file=sys.stderr)
        return 1
    try:
        raise SentryCheckError(
            f"Headroom API Sentry check {datetime.now(UTC).isoformat()}"
        )
    except SentryCheckError as exc:
        event_id = sentry_sdk.capture_exception(exc)
    sentry_sdk.flush(timeout=FLUSH_TIMEOUT_SECONDS)
    if event_id is None:
        print("Sentry did not accept the event", file=sys.stderr)
        return 1
    print(event_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
