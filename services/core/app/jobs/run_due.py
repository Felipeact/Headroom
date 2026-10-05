"""Run every job that is due, then exit: `python -m app.jobs.run_due` (spec 15).

Railway's `jobs` service starts this every hour and expects it to exit. Exit code 0
means the run finished, even when a job or a bank sync failed (those are logged and
retried later); 1 means the runner itself could not start.
"""

import sys
from datetime import UTC, datetime

import structlog
from sqlalchemy import text

from app import jobs, subscriptions
from app.db import get_engine
from app.log import configure_logging
from app.monitoring import init_sentry
from app.settings import get_settings

log = structlog.get_logger(__name__)

# Per job name, the counts the job returned.
RunSummary = dict[str, dict[str, int]]


def run_due(now: datetime) -> RunSummary:
    """Run every job in `jobs.JOBS` as of `now`; one failing job does not stop the rest."""
    summary: RunSummary = {}
    for job in jobs.JOBS:
        name = job.__name__
        try:
            summary[name] = job(now)
        except Exception as exc:  # noqa: BLE001 - the next jobs still run
            log.error("jobs.job_failed", job=name, error_type=type(exc).__name__)
    log.info(
        "jobs.run_finished",
        **{key: value for counts in summary.values() for key, value in counts.items()},
    )
    return summary


def main() -> int:
    configure_logging()
    try:
        settings = get_settings()
        init_sentry(settings)
        subscriptions.register()
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 - reported as the exit code, never the text
        log.error("jobs.run_failed", error_type=type(exc).__name__)
        return 1
    try:
        run_due(datetime.now(UTC))
    finally:
        get_engine().dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
