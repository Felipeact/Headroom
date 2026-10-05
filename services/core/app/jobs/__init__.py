"""The hourly jobs (spec 15): `python -m app.jobs.run_due` runs every job in `JOBS`.

A job is a function of the current time. It decides for itself what is due then, gives
the same result if it runs twice, and returns counts for the run's log line.
"""

from collections.abc import Callable
from datetime import datetime

from app.jobs.nightly import nightly_bank_sync

Job = Callable[[datetime], dict[str, int]]

JOBS: tuple[Job, ...] = (nightly_bank_sync,)
