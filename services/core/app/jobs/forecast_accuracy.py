"""Spec 22: pin each week's forecast and record how far earlier ones were off."""

from datetime import datetime

from app.modules.forecasting import service


def forecast_accuracy(now: datetime) -> dict[str, int]:
    """Pin and record what is due at `now`; returns the counts for `jobs.run_finished`."""
    return service.record_forecast_accuracy(now)
