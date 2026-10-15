"""Spec 32: the weekly_metrics job, from the clock to the email (C25-C27, C29, C30)."""

import importlib
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

import app.main  # noqa: F401 - registers every module's tables on Base.metadata
from app import jobs
from app.db import Base, get_sessionmaker
from app.jobs.run_due import run_due
from app.jobs.weekly_metrics import weekly_metrics
from app.log import configure_logging
from app.settings import get_settings
from tests.email_support import Mail, log_lines
from tests.metrics_support import SIGNUP, FakePostHogQuery, clear, owner_with_business

# `app.jobs.weekly_metrics` is the job function; the module is in sys.modules.
job_module = importlib.import_module("app.jobs.weekly_metrics")

pytestmark = pytest.mark.usefixtures("isolated_database")

TWO = " a@example.test, b@example.test "


def at(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, mail: Mail) -> Iterator[FakePostHogQuery]:
    clear()
    query = FakePostHogQuery(weekly_active=3, alerts_opened=2)
    monkeypatch.setattr(job_module, "get_posthog_query", lambda: query)
    monkeypatch.setenv("METRICS_REPORT_RECIPIENTS", TWO)
    get_settings.cache_clear()
    yield query
    get_settings.cache_clear()


def test_only_tuesday_at_noon_utc(fake: FakePostHogQuery, mail: Mail) -> None:
    """C25."""
    for due in (at(10, 27, 12, 0), at(10, 27, 12, 59)):
        assert weekly_metrics(due) == {"metrics_reports": 2}
    sent = len(mail.sender.sent)
    queried = len(fake.queries)
    assert sent == 4

    for early in (
        at(10, 27, 11, 59),
        at(10, 27, 13, 0),
        at(10, 26, 12, 5),
        at(10, 28, 12, 5),
    ):
        assert weekly_metrics(early) == {"metrics_reports": 0}
    assert len(mail.sender.sent) == sent
    assert len(fake.queries) == queried


def test_report_week_is_the_week_before(fake: FakePostHogQuery, mail: Mail) -> None:
    """C26."""
    weekly_metrics(at(10, 27, 12, 5))
    weekly_metrics(at(11, 3, 12, 5))

    first, _, second, _ = mail.sender.sent
    assert first.subject == "Headroom metrics, Oct 19 to Oct 25"
    assert "Mon, Oct 19" in first.text and "Sun, Oct 25" in first.text
    assert second.subject == "Headroom metrics, Oct 26 to Nov 1"
    assert "Mon, Oct 26" in second.text and "Sun, Nov 1" in second.text


def test_recipients(
    fake: FakePostHogQuery,
    mail: Mail,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C27."""
    configure_logging()
    assert weekly_metrics(at(10, 27, 12, 5)) == {"metrics_reports": 2}
    assert [e.to for e in mail.sender.sent] == ["a@example.test", "b@example.test"]

    for value in ("", "  "):
        mail.sender.sent.clear()
        monkeypatch.setenv("METRICS_REPORT_RECIPIENTS", value)
        get_settings.cache_clear()
        capsys.readouterr()
        assert weekly_metrics(at(10, 27, 12, 5)) == {"metrics_reports": 0}
        assert mail.sender.sent == []
        events = [l["event"] for l in log_lines(capsys.readouterr().out)]
        assert "metrics.report_skipped" in events

    monkeypatch.delenv("METRICS_REPORT_RECIPIENTS")
    get_settings.cache_clear()
    capsys.readouterr()
    assert weekly_metrics(at(10, 27, 12, 5)) == {"metrics_reports": 0}
    events = [l["event"] for l in log_lines(capsys.readouterr().out)]
    assert "metrics.report_skipped" in events


def test_second_run_repeats_without_state(fake: FakePostHogQuery, mail: Mail) -> None:
    """C29."""
    owner_with_business(SIGNUP)

    def counts() -> dict[str, int]:
        with get_sessionmaker()() as session:
            return {
                table.name: session.scalar(select(func.count()).select_from(table)) or 0
                for table in Base.metadata.sorted_tables
            }

    weekly_metrics(at(10, 27, 12, 5))
    before = counts()
    weekly_metrics(at(10, 27, 12, 35))

    assert len(mail.sender.sent) == 4
    assert counts() == before


def test_registered_in_jobs(fake: FakePostHogQuery, mail: Mail) -> None:
    """C30."""
    names = [job.__name__ for job in jobs.JOBS]
    assert names == [
        "nightly_bank_sync",
        "forecast_accuracy",
        "weekly_metrics",
        "weekly_digest",
        "email_retries",
    ]

    summary = run_due(at(10, 27, 12, 5))

    assert summary["weekly_metrics"] == {"metrics_reports": 2}
    keys = [key for counts in summary.values() for key in counts]
    assert len(keys) == len(set(keys))
