"""Spec 32: email the weekly metrics report, Tuesdays in the 12 o'clock hour (UTC)."""

from datetime import UTC, datetime

import structlog

from app import metrics
from app.analytics import get_posthog_query
from app.db import get_sessionmaker
from app.modules.notifications import service as notifications_service
from app.settings import get_settings

log = structlog.get_logger(__name__)

TUESDAY = 1
SEND_HOUR = 12


def _params(report: metrics.WeeklyMetrics) -> dict[str, object]:
    return {
        "week_start": report.week_start.isoformat(),
        "week_end": report.week_end.isoformat(),
        "weekly_active_businesses": report.weekly_active_businesses,
        "alerts_opened": report.alerts_opened,
        "signups": report.signups,
        "activated": report.activated,
        "activation_percent": report.activation_percent,
        "forecast_error_percent": report.forecast_error_percent,
        "forecast_error_businesses": report.forecast_error_businesses,
    }


def weekly_metrics(now: datetime) -> dict[str, int]:
    """Send the report if `now` is Tuesday in the 12 o'clock hour UTC; returns the count sent.

    The Tuesday hour is the first one in which every Canadian time zone has recorded the
    previous week's forecast errors (AD-085). A missed run loses that week's report and a
    second run in the hour sends it again; neither changes any stored state.
    """
    moment = now.astimezone(UTC)
    if moment.weekday() != TUESDAY or moment.hour != SEND_HOUR:
        return {"metrics_reports": 0}
    recipients = get_settings().metrics_report_recipients
    if not recipients:
        log.info("metrics.report_skipped", reason="no_recipients")
        return {"metrics_reports": 0}
    with get_sessionmaker()() as session:
        report = metrics.compute(session, now=moment, query=get_posthog_query())
    sent = notifications_service.send_metrics_report(recipients, _params(report))
    log.info("metrics.report_sent", sent=sent)
    return {"metrics_reports": sent}
