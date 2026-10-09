"""Spec 24: the cash gap check, on hand-built forecasts (C6, C8-C17, C19, C20, C29)."""

import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import events, subscriptions
from app.db import get_sessionmaker
from app.main import app
from app.modules.alerts import service as alerts_service
from app.modules.alerts.models import Alert, AlertItem
from app.modules.forecasting import service as forecasting_service
from app.modules.forecasting.models import MinimumBalance
from tests.test_expected_payments_api import owner_business
from tests.test_forecast_recompute import (
    _registered_and_clock,  # noqa: F401 - autouse: handlers subscribed, clocks fixed
    latest,
    synced_cash,
)
from tests.test_transaction_sync import (
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

MONDAYS = [date(2026, 9, 28) + timedelta(weeks=n) for n in range(13)]
MINIMUM = 500000
ALERT_EVENTS = ("alert.created", "alert.updated", "alert.resolved")
NOW = datetime(2026, 9, 26, 10, 0, tzinfo=UTC)


@dataclass
class Fake:
    """What `forecasting.service` answers, per business."""

    forecasts: dict[uuid.UUID, forecasting_service.ForecastView] = field(
        default_factory=dict
    )
    minimums: dict[uuid.UUID, tuple[int, str]] = field(default_factory=dict)


def install_fake(monkeypatch: pytest.MonkeyPatch) -> Fake:
    """Answer `forecasting.service`'s two reads from a `Fake`, and fix the clock."""
    found = Fake()

    def latest_forecast(
        session: Session, *, business_id: uuid.UUID, now: datetime
    ) -> forecasting_service.ForecastView | None:
        return found.forecasts.get(business_id)

    def minimum_balance_amount(
        session: Session, *, business_id: uuid.UUID
    ) -> tuple[int, str] | None:
        return found.minimums.get(business_id)

    monkeypatch.setattr(forecasting_service, "latest_forecast", latest_forecast)
    monkeypatch.setattr(
        forecasting_service, "minimum_balance_amount", minimum_balance_amount
    )
    monkeypatch.setattr(alerts_service, "clock", lambda: NOW)
    return found


@contextmanager
def listening() -> Iterator[list[events.Event]]:
    """Every alert event published inside the block."""
    seen: list[events.Event] = []
    for name in ALERT_EVENTS:
        events.subscribe(name, seen.append)
    try:
        yield seen
    finally:
        for name in ALERT_EVENTS:
            events.unsubscribe(name, seen.append)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Fake:
    return install_fake(monkeypatch)


@pytest.fixture
def sent() -> Iterator[list[events.Event]]:
    with listening() as seen:
        yield seen


def forecast(
    shortfalls: dict[int, int],
    items: list[forecasting_service.ForecastItemView] | None = None,
) -> forecasting_service.ForecastView:
    """13 weeks at 1000000, except week n ending at MINIMUM - shortfalls[n]."""
    return forecasting_service.ForecastView(
        id=uuid.uuid4(),
        as_of=date(2026, 9, 26),
        computed_at=NOW,
        strategy="recurring_pattern",
        currency="CAD",
        opening_balance_cents=1000000,
        incomplete=False,
        weeks=[
            forecasting_service.ForecastWeekView(
                number=n,
                starts_on=m,
                ends_on=m + timedelta(days=6),
                end_balance_cents=MINIMUM - shortfalls[n]
                if n in shortfalls
                else 1000000,
                low_cents=0,
                high_cents=0,
                money_in_cents=0,
                money_out_cents=0,
                item_ids=[],
            )
            for n, m in enumerate(MONDAYS, 1)
        ],
        items=items or [],
    )


def payroll(day: date) -> forecasting_service.ForecastItemView:
    return forecasting_service.ForecastItemView(
        id=uuid.uuid4(),
        date=day,
        account_id=uuid.uuid4(),
        amount_cents=-1120000,
        currency="CAD",
        source="recurring_pattern",
        source_id=uuid.uuid4(),
        description="Payroll",
        counterparty="Payroll",
        schedule="biweekly",
    )


def business(fake: Fake, **shortfalls: int) -> uuid.UUID:
    _, business_id = owner_business("Alerts")
    found = uuid.UUID(business_id)
    fake.minimums[found] = (MINIMUM, "CAD")
    fake.forecasts[found] = forecast({int(k[1:]): v for k, v in shortfalls.items()})
    return found


def check(
    business_id: uuid.UUID, name: str = "forecast.updated", **payload: Any
) -> None:
    alerts_service.check_cash_gaps(
        events.Event(name=name, business_id=business_id, payload=payload)
    )


def alerts_of(business_id: uuid.UUID) -> list[Alert]:
    with get_sessionmaker()() as session:
        found = list(
            session.scalars(
                select(Alert)
                .where(Alert.business_id == business_id)
                .order_by(Alert.created_at, Alert.starts_on, Alert.id)
            )
        )
        session.expunge_all()
    return found


def items_of(alert_id: uuid.UUID) -> list[tuple[Any, ...]]:
    with get_sessionmaker()() as session:
        return [
            (i.position, i.kind, i.date, i.amount_cents, i.description)
            for i in session.scalars(
                select(AlertItem)
                .where(AlertItem.alert_id == alert_id)
                .order_by(AlertItem.position)
            )
        ]


def columns(alert: Alert) -> dict[str, Any]:
    return {c.key: getattr(alert, c.key) for c in Alert.__table__.columns}


def payloads(seen: list[events.Event]) -> list[tuple[str, dict[str, Any]]]:
    return [(e.name, dict(e.payload)) for e in seen]


def dismiss(business_id: uuid.UUID, alert_id: uuid.UUID) -> None:
    with get_sessionmaker()() as session:
        alerts_service.dismiss_alert(
            session, business_id=business_id, alert_id=alert_id, now=NOW
        )


def test_new_gap_creates_one_alert(fake: Fake, sent: list[events.Event]) -> None:
    """C6."""
    business_id = business(fake, w7=185000)
    seen_rows: list[int] = []

    def count(event: events.Event) -> None:
        seen_rows.append(len(alerts_of(event.business_id)))

    events.subscribe("alert.created", count)
    try:
        check(business_id)
    finally:
        events.unsubscribe("alert.created", count)
    (alert,) = alerts_of(business_id)
    assert alert.state == "open"
    assert payloads(sent) == [("alert.created", {"alert_id": str(alert.id)})]
    assert seen_rows == [1]


def test_nothing_without_forecast_or_minimum(
    fake: Fake, sent: list[events.Event]
) -> None:
    """C8."""
    no_minimum = business(fake, w7=185000)
    del fake.minimums[no_minimum]
    no_forecast = business(fake, w7=185000)
    del fake.forecasts[no_forecast]
    for business_id in (no_minimum, no_forecast):
        check(business_id)
        assert alerts_of(business_id) == []
    assert sent == []


def test_same_forecast_twice(fake: Fake, sent: list[events.Event]) -> None:
    """C9."""
    business_id = business(fake, w7=185000)
    fake.forecasts[business_id].items.append(payroll(date(2026, 11, 13)))
    check(business_id)
    (first,) = alerts_of(business_id)
    before = (columns(first), items_of(first.id))
    assert len(before[1]) == 1
    sent.clear()
    check(business_id)
    (second,) = alerts_of(business_id)
    assert (columns(second), items_of(second.id)) == before
    assert sent == []


def test_overlapping_gap_is_the_same_alert(
    fake: Fake, sent: list[events.Event]
) -> None:
    """C10."""
    business_id = business(fake, w7=185000)
    check(business_id)
    (alert,) = alerts_of(business_id)
    fake.forecasts[business_id] = forecast({6: 100000, 7: 185000})
    check(business_id)
    (moved,) = alerts_of(business_id)
    assert moved.id == alert.id
    assert moved.starts_on == date(2026, 11, 2)
    fake.forecasts[business_id] = forecast({6: 100000, 7: 185000, 8: 50000})
    check(business_id)
    (grown,) = alerts_of(business_id)
    assert grown.id == alert.id
    assert (grown.starts_on, grown.ends_on) == (date(2026, 11, 2), date(2026, 11, 22))


@pytest.mark.parametrize(("before", "after"), [(185000, 285001), (100000, 120001)])
def test_growth_announced(
    fake: Fake, sent: list[events.Event], before: int, after: int
) -> None:
    """C11."""
    business_id = business(fake, w7=before)
    check(business_id)
    (alert,) = alerts_of(business_id)
    sent.clear()
    fake.forecasts[business_id] = forecast({7: after})
    check(business_id)
    assert payloads(sent) == [("alert.updated", {"alert_id": str(alert.id)})]
    (grown,) = alerts_of(business_id)
    assert (grown.shortfall_cents, grown.notified_shortfall_cents) == (after, after)


@pytest.mark.parametrize(
    ("before", "after"), [(600000, 700000), (400000, 480000), (185000, 100000)]
)
def test_small_change_silent(
    fake: Fake, sent: list[events.Event], before: int, after: int
) -> None:
    """C12."""
    business_id = business(fake, w7=before)
    check(business_id)
    sent.clear()
    fake.forecasts[business_id] = forecast({7: after})
    check(business_id)
    assert sent == []
    (alert,) = alerts_of(business_id)
    assert (alert.shortfall_cents, alert.notified_shortfall_cents) == (after, before)


def test_minimum_change_rechecks() -> None:
    """C13: through the API, with the real forecast and the registered handlers."""
    cash, _ = synced_cash()
    business_id = uuid.UUID(cash.business_id)
    snapshot = latest(business_id)
    assert alerts_of(business_id) == []
    response = client.put(
        f"/v1/businesses/{cash.business_id}/minimum-balance",
        json={"amount_cents": 1_000_000_000},
        headers=cash.caller.headers,
    )
    assert response.status_code == 200, response.text
    (alert,) = alerts_of(business_id)
    assert alert.state == "open"
    assert latest(business_id).id == snapshot.id


def test_other_sources_ignored() -> None:
    """C14."""
    cash, _ = synced_cash()
    business_id = uuid.UUID(cash.business_id)
    with get_sessionmaker()() as session:
        session.add(
            MinimumBalance(
                business_id=business_id,
                amount_cents=1_000_000_000,
                currency="CAD",
                updated_by=uuid.uuid4(),
            )
        )
        session.commit()
    check(business_id, "forecast_inputs.changed", source="expected_payments")
    assert alerts_of(business_id) == []
    check(business_id, "forecast_inputs.changed", source="minimum_balance")
    assert len(alerts_of(business_id)) == 1


def test_concurrent_checks_one_alert(fake: Fake, sent: list[events.Event]) -> None:
    """C15."""
    business_id = business(fake, w7=185000)
    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def run() -> None:
        start.wait()
        try:
            check(business_id)
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert len(alerts_of(business_id)) == 1
    assert [e.name for e in sent] == ["alert.created"]


@pytest.mark.parametrize("dismissed", [False, True])
def test_gap_gone_resolves(
    fake: Fake, sent: list[events.Event], dismissed: bool
) -> None:
    """C16."""
    business_id = business(fake, w7=185000)
    check(business_id)
    (alert,) = alerts_of(business_id)
    if dismissed:
        dismiss(business_id, alert.id)
    sent.clear()
    fake.forecasts[business_id] = forecast({})
    check(business_id)
    (gone,) = alerts_of(business_id)
    assert gone.state == "resolved"
    assert gone.resolved_at == NOW
    assert payloads(sent) == [("alert.resolved", {"alert_id": str(alert.id)})]


def test_resolved_never_reused(fake: Fake, sent: list[events.Event]) -> None:
    """C17."""
    business_id = business(fake, w7=185000)
    check(business_id)
    (original,) = alerts_of(business_id)
    fake.forecasts[business_id] = forecast({})
    check(business_id)
    sent.clear()
    fake.forecasts[business_id] = forecast({7: 185000})
    check(business_id)
    both = alerts_of(business_id)
    assert len(both) == 2
    (first,) = [a for a in both if a.id == original.id]
    (second,) = [a for a in both if a.id != original.id]
    assert first.state == "resolved"
    assert second.state == "open"
    assert second.id != first.id
    assert payloads(sent) == [("alert.created", {"alert_id": str(second.id)})]


def test_dismissed_grows_reopens(fake: Fake, sent: list[events.Event]) -> None:
    """C19."""
    business_id = business(fake, w7=185000)
    check(business_id)
    (alert,) = alerts_of(business_id)
    dismiss(business_id, alert.id)
    sent.clear()
    fake.forecasts[business_id] = forecast({7: 285001})
    check(business_id)
    (reopened,) = alerts_of(business_id)
    assert (reopened.state, reopened.dismissed_at) == ("open", None)
    assert payloads(sent) == [("alert.updated", {"alert_id": str(alert.id)})]


def test_dismissed_small_change_stays(fake: Fake, sent: list[events.Event]) -> None:
    """C20."""
    business_id = business(fake, w7=185000)
    check(business_id)
    (alert,) = alerts_of(business_id)
    dismiss(business_id, alert.id)
    sent.clear()
    fake.forecasts[business_id] = forecast({7: 200000})
    check(business_id)
    (kept,) = alerts_of(business_id)
    assert (kept.state, kept.shortfall_cents) == ("dismissed", 200000)
    assert sent == []


def test_subscriptions() -> None:
    """C29."""
    assert subscriptions.SUBSCRIPTIONS[4] == (
        "forecast.updated",
        alerts_service.check_cash_gaps,
    )
    assert subscriptions.SUBSCRIPTIONS[5] == (
        "forecast_inputs.changed",
        alerts_service.check_cash_gaps,
    )
    assert len(subscriptions.SUBSCRIPTIONS) == 6
