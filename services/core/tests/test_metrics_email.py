"""Spec 32: what the report email says (C24 email half, C28)."""

import re

import pytest

from app import metrics
from app.analytics import PostHogError
from app.db import get_sessionmaker
from app.jobs.weekly_metrics import _params
from app.modules.notifications import service as notifications_service
from tests.email_support import Mail
from tests.metrics_support import (
    NOW,
    SIGNUP,
    WEEK,
    FakePostHogQuery,
    accuracy,
    clear,
    connection,
    owner_with_business,
)

pytestmark = pytest.mark.usefixtures("isolated_database")

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def send(mail: Mail, query: FakePostHogQuery) -> tuple[str, str, str]:
    with get_sessionmaker()() as session:
        report = metrics.compute(session, now=NOW, query=query)
    assert (
        notifications_service.send_metrics_report(["ops@example.test"], _params(report))
        == 1
    )
    (email,) = mail.sender.sent
    return email.subject, email.text, email.html


def test_aggregates_only(mail: Mail) -> None:
    """C28."""
    clear()
    _, business_id = owner_with_business(SIGNUP, "Harbor Street Plumbing")
    connection(business_id, SIGNUP)
    accuracy(business_id, target_week=WEEK, horizon=4, forecast=110, actual=100)

    subject, text, html = send(mail, FakePostHogQuery(weekly_active=3, alerts_opened=2))

    for body in (subject, text, html):
        assert "Harbor Street" not in body
        assert UUID.search(body) is None
        assert str(business_id) not in body
    assert "Weekly active businesses: 3" in text
    assert "Alerts opened: 2" in text
    assert "Activation: 100% (1 of 1)" in text
    assert "4-week forecast error: 10.0% across 1 business" in text
    for definition in (
        "Businesses where someone opened the dashboard.",
        "Different alerts someone opened.",
        "New owners who connected a bank within 24 hours of signing up.",
        "How far the forecast made four weeks earlier was from the actual balance",
    ):
        assert definition in text
        assert definition in html
    assert "Mon, Oct 19" in text and "Sun, Oct 25" in text


def test_empty_week_says_so(mail: Mail) -> None:
    """C21, C23: no sign-ups and no error data are words, never zeros."""
    clear()

    _, text, html = send(mail, FakePostHogQuery())

    for body in (text, html):
        assert "no sign-ups" in body
        assert "no data yet" in body
        assert re.search(r"(?<![0-9])0%", body) is None


def test_posthog_failure_says_unavailable_twice(mail: Mail) -> None:
    """C24."""
    clear()
    owner_with_business(SIGNUP)

    _, text, _ = send(mail, FakePostHogQuery(error=PostHogError(error_type="timeout")))

    assert text.count("unavailable") == 2
    assert "Activation: 0% (0 of 1)" in text
