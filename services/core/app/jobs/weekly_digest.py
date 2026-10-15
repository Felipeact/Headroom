"""Spec 30: email each business's owners their weekly digest, Mondays in the 8 AM hour."""

from datetime import datetime

from app.modules.notifications import service


def weekly_digest(now: datetime) -> dict[str, int]:
    """Send the digests due at `now`; returns the counts for `jobs.run_finished`."""
    return service.send_weekly_digests(now)
