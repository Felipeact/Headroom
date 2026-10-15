"""Spec 32 C32: the report's settings are optional and parse as lists."""

import importlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.settings import Settings, get_settings

NAMES = (
    "POSTHOG_APP_HOST",
    "POSTHOG_PROJECT_ID",
    "POSTHOG_PERSONAL_API_KEY",
    "METRICS_REPORT_RECIPIENTS",
)


@pytest.fixture(autouse=True)
def fresh_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # A directory with no .env.local, so a developer's PostHog keys never reach the test.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://h:5432/d")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_settings_load_without_them(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)
    settings = Settings()
    assert settings.posthog_app_host is None
    assert settings.posthog_project_id is None
    assert settings.posthog_personal_api_key is None
    assert settings.metrics_report_recipients == []


def test_recipients_are_a_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("METRICS_REPORT_RECIPIENTS", "a@x.test,b@x.test")
    assert Settings().metrics_report_recipients == [
        "a@x.test",
        "b@x.test",
    ]


def test_blank_posthog_settings_are_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in NAMES[:3]:
        monkeypatch.setenv(name, " ")
    settings = Settings()
    assert settings.posthog_project_id is None


def test_the_api_and_the_jobs_process_share_one_settings_reader() -> None:
    """The job reads `get_settings` from `app.settings`, the one the API reads."""
    # `app.jobs.weekly_metrics` is the job function; the module is in sys.modules.
    module = importlib.import_module("app.jobs.weekly_metrics")

    assert module.get_settings is get_settings
