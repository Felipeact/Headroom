"""Spec 28: the hourly retries (C21, C22, C24), on a database of their own."""

from datetime import UTC, datetime

import pytest

from app.jobs.email_retries import email_retries
from app.modules.notifications.senders import SendError
from tests.email_support import Mail

pytestmark = pytest.mark.usefixtures("isolated_database")

NOW = datetime(2026, 10, 20, 6, tzinfo=UTC)


def unavailable() -> SendError:
    return SendError(error_type="503_service_unavailable", retryable=True)


def test_retried_until_sent(mail: Mail) -> None:
    """C21: two failures, then a send on the second run; nothing more after."""
    user = mail.user()
    mail.sender.fail_next(unavailable(), unavailable())

    mail.request(user)
    assert mail.deliveries(user)[0].state == "pending"
    email_retries(NOW)
    assert mail.deliveries(user)[0].state == "pending"
    email_retries(NOW)

    [row] = mail.deliveries(user)
    assert row.state == "sent"
    assert row.attempts == 3
    assert len(mail.sender.sent) == 1
    assert email_retries(NOW) == {
        "emails_sent": 0,
        "emails_failed": 0,
        "emails_pending": 0,
    }
    assert len(mail.sender.sent) == 1


def test_no_attempt_cap(mail: Mail) -> None:
    """C22: after 50 failed attempts the 51st run still tries."""
    user = mail.user()
    mail.sender.fail_next(*(unavailable() for _ in range(50)))

    mail.request(user)
    for _ in range(49):
        email_retries(NOW)
    assert mail.deliveries(user)[0].attempts == 50
    assert mail.deliveries(user)[0].state == "pending"

    email_retries(NOW)

    [row] = mail.deliveries(user)
    assert row.attempts == 51
    assert row.state == "sent"


def test_counts(mail: Mail) -> None:
    """C24: one sent, one failed, one still pending; terminal rows aren't attempted."""
    sends = mail.user(email="sends@example.test")
    fails = mail.user(email="fails@example.test")
    waits = mail.user(email="waits@example.test")
    for user in (sends, fails, waits):
        mail.sender.fail_next(unavailable())
        mail.request(user)
    done = mail.user(email="done@example.test")
    mail.request(done, key="done")
    mail.set_preferences(done, alerts=False, weekly_digest=True)
    mail.request(done, key="skipped")
    mail.sender.fail_to["fails@example.test"] = SendError(
        error_type="422_invalid_parameter", retryable=False
    )
    mail.sender.fail_to["waits@example.test"] = unavailable()
    calls_before = mail.sender.calls

    counts = email_retries(NOW)

    assert counts == {"emails_sent": 1, "emails_failed": 1, "emails_pending": 1}
    assert mail.sender.calls - calls_before == 3


def test_render_error_fails_one_row_and_spares_the_rest(mail: Mail) -> None:
    """A row whose template cannot render is `failed`; the rows after it still send."""
    bad = mail.user(email="bad@example.test")
    good = mail.user(email="good@example.test")
    mail.request(bad, key="bad", params={"body": "no heading"}, deliver=False)
    mail.sender.fail_next(unavailable())
    mail.request(good, key="good")

    email_retries(NOW)

    # This module's database is shared, so judge the two rows, not the run's totals.
    assert mail.deliveries(bad)[0].state == "failed"
    assert mail.deliveries(good)[0].state == "sent"
    assert [email.to for email in mail.sender.sent] == ["good@example.test"]
