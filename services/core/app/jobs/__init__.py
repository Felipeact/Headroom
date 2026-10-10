"""The hourly jobs (spec 15): `python -m app.jobs.run_due` runs every job in `JOBS`.

A job is a function of the current time. It decides for itself what is due then, gives
the same result if it runs twice, and returns counts for the run's log line.
"""

from collections.abc import Callable
from datetime import datetime

from app.jobs.email_retries import email_retries
from app.jobs.forecast_accuracy import forecast_accuracy
from app.jobs.nightly import nightly_bank_sync

Job = Callable[[datetime], dict[str, int]]

# The nightly sync first, so a fresh balance is there when both are due (AD-085).
JOBS: tuple[Job, ...] = (nightly_bank_sync, forecast_accuracy, email_retries)
