"""The weekly metrics report's figures (spec 32, door 6).

Like `app/dashboard.py` (AD-102) this composes several modules' public functions and owns no
table or event: sign-ups from `accounts`, first bank connections from `bank_sync`, the stored
forecast errors from `forecasting`, and the two figures only PostHog holds. A figure that
cannot be computed is None, never zero.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import structlog
from sqlalchemy.orm import Session

from app.analytics import PostHogError, PostHogQuery
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync import service as bank_sync_service
from app.modules.forecasting import service as forecasting_service

log = structlog.get_logger(__name__)

ACTIVATION_WINDOW = timedelta(hours=24)
FORECAST_ERROR_HORIZON = 4


@dataclass(frozen=True)
class WeeklyMetrics:
    # Monday and Sunday of the report week (UTC dates).
    week_start: date
    week_end: date
    # From PostHog; None when it could not be asked.
    weekly_active_businesses: int | None
    alerts_opened: int | None
    # Users who signed up in the week, how many connected a bank within 24 hours, and the
    # whole percent; None without sign-ups.
    signups: int
    activated: int
    activation_percent: int | None
    # Mean 4-week forecast error in percent to one decimal over `forecast_error_businesses`
    # businesses; None when no business has a record for the week.
    forecast_error_percent: float | None
    forecast_error_businesses: int


def report_week(now: datetime) -> tuple[date, date]:
    """The Monday and Sunday (UTC) of the week before the one `now` falls in."""
    today = now.astimezone(UTC).date()
    monday = today - timedelta(days=today.weekday() + 7)
    return monday, monday + timedelta(days=6)


def _bounds(week_start: date) -> tuple[datetime, datetime]:
    start = datetime.combine(week_start, time.min, tzinfo=UTC)
    return start, start + timedelta(days=7)


def _count_events(
    query: PostHogQuery | None, *, event: str, key: str, start: datetime, end: datetime
) -> int | None:
    if query is None:
        log.warning("metrics.posthog_failed", error_type="not_configured")
        return None
    fmt = "%Y-%m-%d %H:%M:%S"
    hogql = (
        f"SELECT count(distinct properties.{key}) FROM events"
        f" WHERE event = '{event}'"
        f" AND timestamp >= toDateTime('{start.strftime(fmt)}', 'UTC')"
        f" AND timestamp < toDateTime('{end.strftime(fmt)}', 'UTC')"
    )
    try:
        return query.count(hogql)
    except PostHogError as exc:
        log.warning("metrics.posthog_failed", error_type=exc.error_type)
        return None


def _activation(
    session: Session, *, start: datetime, end: datetime
) -> tuple[int, int, int | None]:
    cohort = accounts_service.signup_cohort(session, start=start, end=end)
    first_connected = bank_sync_service.first_connection_times(
        session, business_ids=[b for s in cohort for b in s.owned_business_ids]
    )
    activated = sum(
        1
        for signup in cohort
        if any(
            business in first_connected
            and first_connected[business] <= signup.created_at + ACTIVATION_WINDOW
            for business in signup.owned_business_ids
        )
    )
    if not cohort:
        return 0, 0, None
    # Whole percent, half up.
    return len(cohort), activated, (200 * activated + len(cohort)) // (2 * len(cohort))


def _forecast_error(session: Session, *, week_start: date) -> tuple[float | None, int]:
    records = forecasting_service.accuracy_history(
        session,
        horizon=FORECAST_ERROR_HORIZON,
        since=week_start - timedelta(weeks=FORECAST_ERROR_HORIZON - 1),
    )
    percents = [
        r.error_percent
        for r in records
        if r.target_week_start == week_start and r.error_percent is not None
    ]
    if not percents:
        return None, 0
    return round(sum(percents) / len(percents), 1), len(percents)


def compute(
    session: Session, *, now: datetime, query: PostHogQuery | None
) -> WeeklyMetrics:
    """The four figures for the week before the one `now` falls in."""
    week_start, week_end = report_week(now)
    start, end = _bounds(week_start)
    signups, activated, percent = _activation(session, start=start, end=end)
    error, error_businesses = _forecast_error(session, week_start=week_start)
    return WeeklyMetrics(
        week_start=week_start,
        week_end=week_end,
        weekly_active_businesses=_count_events(
            query, event="dashboard_viewed", key="business_id", start=start, end=end
        ),
        alerts_opened=_count_events(
            query, event="alert_opened", key="alert_id", start=start, end=end
        ),
        signups=signups,
        activated=activated,
        activation_percent=percent,
        forecast_error_percent=error,
        forecast_error_businesses=error_businesses,
    )
