"""Retry every email still pending (spec 28): one attempt each, every hour, until sent."""

from datetime import datetime

from app.modules.notifications import service as notifications_service


def email_retries(now: datetime) -> dict[str, int]:
    """Attempt each pending delivery once; returns the sent, failed and pending counts."""
    return notifications_service.retry_pending()
