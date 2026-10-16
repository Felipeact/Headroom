"""Spec 32 C34: did the eight events reach PostHog, with only the allowed properties?

Run from services/core after going through the eight steps in the app:

    uv run python ../../.specs/features/32-launch-analytics-and-metrics/posthog_events.py

Reads POSTHOG_APP_HOST, POSTHOG_PROJECT_ID and POSTHOG_PERSONAL_API_KEY from the environment
(export them from .env.local; nothing is hard-coded or printed). Exit 0 only when each event
was seen in the last 24 hours and no event carries a property outside the allowlist. PostHog's
own `$`-prefixed properties are not ours and are ignored.
"""

import os
import sys

sys.path.insert(0, os.getcwd())

from app.analytics import PostHogError, PostHogHttpQuery  # noqa: E402

EVENTS = (
    "sign_up_completed",
    "business_created",
    "bank_connected",
    "minimum_balance_set",
    "dashboard_viewed",
    "alert_opened",
    "alert_dismissed",
    "expected_payment_added",
)
ALLOWED = ("business_id", "alert_id", "role")
SINCE = "timestamp > now() - INTERVAL 24 HOUR"


def main() -> int:
    try:
        query = PostHogHttpQuery(
            app_host=os.environ["POSTHOG_APP_HOST"],
            project_id=os.environ["POSTHOG_PROJECT_ID"],
            personal_api_key=os.environ["POSTHOG_PERSONAL_API_KEY"],
        )
    except KeyError as missing:
        print(f"missing environment variable {missing}")
        return 2
    failed = False
    try:
        for event in EVENTS:
            seen = query.count(f"SELECT count() FROM events WHERE event = '{event}' AND {SINCE}")
            print(f"{'ok  ' if seen else 'MISSING'} {event} ({seen})")
            failed = failed or not seen
        names = ", ".join(f"'{e}'" for e in EVENTS)
        allowed = ", ".join(f"'{k}'" for k in ALLOWED)
        extra = query.count(
            f"SELECT count() FROM events WHERE event IN ({names}) AND {SINCE}"
            f" AND arrayExists(k -> NOT startsWith(k, '$') AND k NOT IN ({allowed}),"
            " JSONExtractKeys(properties))"
        )
    except PostHogError as exc:
        print(f"PostHog query failed: {exc.error_type}")
        return 2
    print(f"{'ok  ' if not extra else 'EXTRA'} events with a property outside {ALLOWED}: {extra}")
    return 1 if failed or extra else 0


if __name__ == "__main__":
    sys.exit(main())
