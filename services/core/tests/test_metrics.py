"""Spec 32: the report's figures, over a database of the module's own (C18-C24, C31).

Week of the report: Monday 2026-10-19 to Sunday 2026-10-25, computed on Tuesday the 27th.
"""

import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import metrics
from app.analytics import PostHogError
from app.db import get_sessionmaker
from app.log import configure_logging
from tests.email_support import log_lines
from tests.metrics_support import (
    NOW,
    SIGNUP,
    WEEK,
    FakePostHogQuery,
    accuracy,
    business,
    clear,
    connection,
    member,
    owner_with_business,
    user,
)

pytestmark = pytest.mark.usefixtures("isolated_database")


@pytest.fixture(autouse=True)
def empty_database() -> None:
    clear()


def compute(query: FakePostHogQuery | None = None) -> metrics.WeeklyMetrics:
    with get_sessionmaker()() as session:
        return metrics.compute(session, now=NOW, query=query or FakePostHogQuery())


def test_weekly_active_query() -> None:
    """C18."""
    fake = FakePostHogQuery(weekly_active=12, alerts_opened=4)
    report = compute(fake)

    assert report.weekly_active_businesses == 12
    (query,) = [q for q in fake.queries if "dashboard_viewed" in q]
    assert "count(distinct properties.business_id)" in query
    assert "timestamp >= toDateTime('2026-10-19 00:00:00', 'UTC')" in query
    assert "timestamp < toDateTime('2026-10-26 00:00:00', 'UTC')" in query


def test_alerts_opened_query() -> None:
    """C19."""
    fake = FakePostHogQuery(weekly_active=12, alerts_opened=4)
    report = compute(fake)

    assert report.alerts_opened == 4
    (query,) = [q for q in fake.queries if "alert_opened" in q]
    assert "count(distinct properties.alert_id)" in query
    assert "timestamp >= toDateTime('2026-10-19 00:00:00', 'UTC')" in query
    assert "timestamp < toDateTime('2026-10-26 00:00:00', 'UTC')" in query


def test_activation_cohort() -> None:
    """C20: A, B, C, D, F are the cohort; A and B connected within 24 hours."""
    hour = timedelta(hours=1)
    minute = timedelta(minutes=1)
    _, a = owner_with_business(SIGNUP)
    connection(a, SIGNUP + 24 * hour - minute)
    _, b = owner_with_business(SIGNUP)
    connection(b, SIGNUP + 24 * hour)
    _, c = owner_with_business(SIGNUP)
    connection(c, SIGNUP + 24 * hour + minute)
    owner_with_business(SIGNUP)  # D: no connection
    e = user(SIGNUP)  # E: only a bookkeeper membership
    member(business(), e, "bookkeeper")
    user(SIGNUP)  # F: no membership at all
    last_week = SIGNUP - timedelta(days=6)
    _, g = owner_with_business(last_week)  # G: signed up the week before
    connection(g, last_week + hour)

    report = compute()

    assert (report.signups, report.activated, report.activation_percent) == (5, 2, 40)


def test_activation_without_signups() -> None:
    """C21."""
    report = compute()

    assert (report.signups, report.activated) == (0, 0)
    assert report.activation_percent is None


def test_forecast_error_mean() -> None:
    """C22: 10.0 and 20.0 count; the null percent, horizon 1 and the other week do not."""
    x = business("X")
    y = business("Y")
    z = business("Z")
    q = business("Q")
    accuracy(x, target_week=WEEK, horizon=4, forecast=110, actual=100)
    accuracy(y, target_week=WEEK, horizon=4, forecast=120, actual=100)
    accuracy(z, target_week=WEEK, horizon=4, forecast=50, actual=0)
    accuracy(q, target_week=WEEK, horizon=1, forecast=999, actual=100)
    accuracy(
        x, target_week=WEEK - timedelta(weeks=1), horizon=4, forecast=500, actual=100
    )

    report = compute()

    assert report.forecast_error_percent == 15.0
    assert report.forecast_error_businesses == 2


def test_forecast_error_none() -> None:
    """C23: nothing for the week, or only null percents."""
    assert compute().forecast_error_percent is None

    accuracy(business("Z"), target_week=WEEK, horizon=4, forecast=50, actual=0)
    report = compute()
    assert report.forecast_error_percent is None
    assert report.forecast_error_businesses == 0


def test_posthog_failure_still_reports(capsys: pytest.CaptureFixture[str]) -> None:
    """C24 (the email half is in test_metrics_email)."""
    configure_logging()
    owner_with_business(SIGNUP)
    fake = FakePostHogQuery(error=PostHogError(error_type="http_500"))

    report = compute(fake)

    assert report.weekly_active_businesses is None
    assert report.alerts_opened is None
    assert report.signups == 1
    failed = [
        l
        for l in log_lines(capsys.readouterr().out)
        if l["event"] == "metrics.posthog_failed"
    ]
    assert [l["error_type"] for l in failed] == ["http_500", "http_500"]
    assert all(
        set(l) <= {"timestamp", "level", "logger", "event", "error_type"}
        for l in failed
    )


def test_an_unconfigured_posthog_reads_unavailable() -> None:
    """C24: no query client at all is the same as a failing one."""
    with get_sessionmaker()() as session:
        report = metrics.compute(session, now=NOW, query=None)
    assert (report.weekly_active_businesses, report.alerts_opened) == (None, None)


def test_report_week_is_the_week_before() -> None:
    """C26 (the dates; the email text is checked with the job)."""
    assert metrics.report_week(NOW) == (WEEK, date(2026, 10, 25))
    assert metrics.report_week(NOW + timedelta(days=7)) == (
        date(2026, 10, 26),
        date(2026, 11, 1),
    )


def test_imports_only_services() -> None:
    """C31."""
    source = Path(metrics.__file__).read_text(encoding="utf8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "app.modules"
        ):
            parts = (node.module or "").split(".")
            if len(parts) == 3:
                assert [a.name for a in node.names] == ["service"], ast.dump(node)
            else:
                assert parts[-1] == "service", ast.dump(node)
        if isinstance(node, ast.ClassDef):
            assert not any(getattr(b, "id", "") == "Base" for b in node.bases)
    assert "subscribe(" not in source
