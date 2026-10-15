"""The hourly jobs (spec 15): `python -m app.jobs.run_due` runs every job in `JOBS`.

A job is a function of the current time. It decides for itself what is due then, gives
the same result if it runs twice, and returns counts for the run's log line.
"""

from collections.abc import Callable
from datetime import datetime

from app.jobs.email_retries import email_retries
from app.jobs.forecast_accuracy import forecast_accuracy
from app.jobs.nightly import nightly_bank_sync
from app.jobs.weekly_digest import weekly_digest

Job = Callable[[datetime], dict[str, int]]

# The nightly sync first, so a fresh balance is there when both are due (AD-085). The
# digest follows the accuracy job, which pins this Monday's forecast, and precedes the
# retries so a digest that fails to send is tried again within the hour.
JOBS: tuple[Job, ...] = (
    nightly_bank_sync,
    forecast_accuracy,
    weekly_digest,
    email_retries,
)
