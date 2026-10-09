"""Cash gap alerts (spec 24): find each gap in the latest forecast and keep one alert per
gap, open, dismissed or resolved.

The alerts module reads the forecast and the minimum balance only through
`forecasting.service`, and owns the `alerts` and `alert_items` tables.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

import structlog
from sqlalchemy.orm import Session

from app import events
from app.db import get_sessionmaker
from app.modules.alerts import gaps, repository
from app.modules.alerts.events import ALERT_CREATED, ALERT_RESOLVED, ALERT_UPDATED
from app.modules.alerts.models import Alert, AlertItem, AlertItemKind, AlertState
from app.modules.forecasting import service as forecasting_service
from app.modules.forecasting.events import FORECAST_INPUTS_CHANGED

log = structlog.get_logger(__name__)

# A shortfall is announced again once it grows by more than either (AC 11).
GROWTH_CENTS = 100_000
GROWTH_PERCENT = 20


class AlertNotFoundError(Exception):
    """No alert with that ID in the business."""


class AlertResolvedError(Exception):
    """A resolved alert can't be dismissed."""


@dataclass(frozen=True)
class AlertItemView:
    kind: AlertItemKind
    date: date
    amount_cents: int
    currency: str
    description: str | None
    counterparty: str | None
    source: str
    schedule: str | None


@dataclass(frozen=True)
class AlertView:
    id: uuid.UUID
    state: AlertState
    starts_on: date
    ends_on: date
    lowest_week_starts_on: date
    lowest_balance_cents: int
    minimum_cents: int
    shortfall_cents: int
    currency: str
    created_at: datetime
    updated_at: datetime
    dismissed_at: datetime | None
    resolved_at: datetime | None
    # Causes first, then the item arriving after the gap.
    items: list[AlertItemView]


def clock() -> datetime:
    """The event handler's clock; tests replace it."""
    return datetime.now(UTC)


def _grew(notified_cents: int, shortfall_cents: int) -> bool:
    growth = shortfall_cents - notified_cents
    return growth > GROWTH_CENTS or growth * 100 > GROWTH_PERCENT * notified_cents


def _rows(alert_id: uuid.UUID, found: list[gaps.Explanation]) -> list[AlertItem]:
    return [
        AlertItem(
            alert_id=alert_id,
            position=n,
            kind=e.kind,
            date=e.date,
            amount_cents=e.amount_cents,
            currency=e.currency,
            description=e.description,
            counterparty=e.counterparty,
            source=e.source,
            source_id=e.source_id,
            schedule=e.schedule,
        )
        for n, e in enumerate(found)
    ]


def _stored(rows: list[AlertItem]) -> list[gaps.Explanation]:
    return [
        gaps.Explanation(
            kind=r.kind,  # type: ignore[arg-type]  # ck_alert_items_kind holds it to AlertItemKind
            date=r.date,
            amount_cents=r.amount_cents,
            currency=r.currency,
            description=r.description,
            counterparty=r.counterparty,
            source=r.source,
            source_id=r.source_id,
            schedule=r.schedule,
        )
        for r in rows
    ]


def _reconcile(
    session: Session, business_id: uuid.UUID, now: datetime
) -> list[tuple[str, uuid.UUID]]:
    """Bring the business's alerts in line with its latest forecast; the events to send."""
    forecast = forecasting_service.latest_forecast(
        session, business_id=business_id, now=now
    )
    minimum = forecasting_service.minimum_balance_amount(
        session, business_id=business_id
    )
    if forecast is None or minimum is None:
        return []
    minimum_cents, currency = minimum
    live = repository.live_alerts(session, business_id=business_id)
    stored = repository.items_of(session, alert_ids=[a.id for a in live])
    pairs, gone = gaps.match(gaps.find_gaps(forecast.weeks, minimum_cents), live)
    sent: list[tuple[str, uuid.UUID]] = []
    for gap, alert in pairs:
        explained = gaps.explain(gap, forecast.items)
        fields = {
            "starts_on": gap.starts_on,
            "ends_on": gap.ends_on,
            "lowest_week_starts_on": gap.lowest_week_starts_on,
            "lowest_balance_cents": gap.lowest_balance_cents,
            "minimum_cents": minimum_cents,
            "shortfall_cents": gap.shortfall_cents,
            "currency": currency,
            "snapshot_id": forecast.id,
        }
        if alert is None:
            alert = Alert(
                id=uuid.uuid4(),
                business_id=business_id,
                state="open",
                notified_shortfall_cents=gap.shortfall_cents,
                created_at=now,
                updated_at=now,
                **fields,
            )
            session.add(alert)
            session.flush()
            repository.replace_items(
                session, alert_id=alert.id, items=_rows(alert.id, explained)
            )
            sent.append((ALERT_CREATED, alert.id))
            continue
        grew = _grew(alert.notified_shortfall_cents, gap.shortfall_cents)
        changed = (
            grew
            or any(getattr(alert, k) != v for k, v in fields.items())
            or _stored(stored.get(alert.id, [])) != explained
        )
        if not changed:
            continue
        for key, value in fields.items():
            setattr(alert, key, value)
        if grew:
            alert.notified_shortfall_cents = gap.shortfall_cents
            alert.state = "open"
            alert.dismissed_at = None
            sent.append((ALERT_UPDATED, alert.id))
        alert.updated_at = now
        repository.replace_items(
            session, alert_id=alert.id, items=_rows(alert.id, explained)
        )
    for alert in gone:
        alert.state = "resolved"
        alert.resolved_at = now
        alert.updated_at = now
        sent.append((ALERT_RESOLVED, alert.id))
    return sent


def check_cash_gaps(event: events.Event) -> None:
    """Re-check the business's cash gaps against its latest forecast and minimum.

    The handler of `forecast.updated` and of `forecast_inputs.changed` with source
    `minimum_balance` (AD-098); any other source returns at once. One transaction under
    the business's alerts lock (AD-096); after the commit it publishes `alert.created`,
    `alert.updated` and `alert.resolved`, one per changed alert. Running it again on the
    same forecast and minimum changes nothing.
    """
    if (
        event.name == FORECAST_INPUTS_CHANGED
        and event.payload.get("source") != "minimum_balance"
    ):
        return
    business_id = event.business_id
    with get_sessionmaker()() as session:
        try:
            repository.lock_alerts(session, business_id=business_id)
            sent = _reconcile(session, business_id, clock())
            session.commit()
        except BaseException:
            session.rollback()
            raise
    for name, alert_id in sent:
        log.info(name, business_id=str(business_id), alert_id=str(alert_id))
        events.publish(
            events.Event(
                name=name, business_id=business_id, payload={"alert_id": str(alert_id)}
            )
        )


def _views(session: Session, alerts: list[Alert]) -> list[AlertView]:
    items = repository.items_of(session, alert_ids=[a.id for a in alerts])
    return [
        AlertView(
            id=a.id,
            state=a.state,  # type: ignore[arg-type]  # ck_alerts_state holds it to AlertState
            starts_on=a.starts_on,
            ends_on=a.ends_on,
            lowest_week_starts_on=a.lowest_week_starts_on,
            lowest_balance_cents=a.lowest_balance_cents,
            minimum_cents=a.minimum_cents,
            shortfall_cents=a.shortfall_cents,
            currency=a.currency,
            created_at=a.created_at,
            updated_at=a.updated_at,
            dismissed_at=a.dismissed_at,
            resolved_at=a.resolved_at,
            items=[
                AlertItemView(
                    kind=i.kind,  # type: ignore[arg-type]  # ck_alert_items_kind
                    date=i.date,
                    amount_cents=i.amount_cents,
                    currency=i.currency,
                    description=i.description,
                    counterparty=i.counterparty,
                    source=i.source,
                    schedule=i.schedule,
                )
                for i in items.get(a.id, [])
            ],
        )
        for a in alerts
    ]


def list_alerts(
    session: Session, *, business_id: uuid.UUID, state: AlertState
) -> list[AlertView]:
    """The business's alerts in `state`, by `starts_on` then `id` (AD-099)."""
    alerts = repository.alerts_in_state(session, business_id=business_id, state=state)
    return _views(session, alerts)


def get_alert(
    session: Session, *, business_id: uuid.UUID, alert_id: uuid.UUID
) -> AlertView:
    """One alert of the business, in any state; raises `AlertNotFoundError`."""
    alert = repository.alert(session, business_id=business_id, alert_id=alert_id)
    if alert is None:
        raise AlertNotFoundError
    return _views(session, [alert])[0]


def dismiss_alert(
    session: Session, *, business_id: uuid.UUID, alert_id: uuid.UUID, now: datetime
) -> AlertView:
    """Dismiss an open alert at its current shortfall (D2); a dismissed one is unchanged.

    Raises `AlertNotFoundError`, or `AlertResolvedError` for a resolved alert. Publishes
    nothing. Commits the session.
    """
    try:
        repository.lock_alerts(session, business_id=business_id)
        alert = repository.alert(session, business_id=business_id, alert_id=alert_id)
        if alert is None:
            raise AlertNotFoundError
        if alert.state == "resolved":
            raise AlertResolvedError
        if alert.state == "open":
            alert.state = "dismissed"
            alert.dismissed_at = now
            alert.notified_shortfall_cents = alert.shortfall_cents
            alert.updated_at = now
        session.commit()
    except BaseException:
        session.rollback()
        raise
    return _views(session, [alert])[0]
