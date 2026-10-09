"""Spec 21: the forecast recomputed on events and stored as snapshots (AD-077, AD-079)."""

import dataclasses
import threading
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import events, subscriptions
from app.db import get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.bank_sync.models import BankAccount
from app.modules.bank_sync.plaid import PlaidAccount, PlaidTransaction
from app.modules.forecasting import engine, repository, service, strategies
from app.modules.forecasting.api import get_now
from app.modules.forecasting.models import (
    ExpectedPayment,
    ExpectedPaymentMatch,
    ForecastItem,
    ForecastSnapshot,
    ForecastWeek,
    RecurringPattern,
)
from app.settings import get_settings
from tests.test_bank_connect import plaid_account
from tests.test_businesses import HARBOR, _owner
from tests.test_expected_payments_api import Cash, cash_business
from tests.test_recurring_refresh import log_lines, rent
from tests.test_transaction_sync import (
    Connected,
    SyncFake,
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
    make_connection,
    page,
    sync,
    tx,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

# 6:00 in Toronto on Saturday 2026-09-26: week 1 starts on Monday 2026-09-28.
NOW = datetime(2026, 9, 26, 10, 0, tzinfo=UTC)
TODAY = date(2026, 9, 26)
MONDAYS = [date(2026, 9, 28) + timedelta(weeks=n) for n in range(13)]


@pytest.fixture(autouse=True)
def _registered_and_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    subscriptions.register()
    monkeypatch.setattr(service, "clock", lambda: NOW)
    app.dependency_overrides[get_now] = lambda: NOW
    yield
    app.dependency_overrides.pop(get_now, None)


@pytest.fixture
def updates() -> Iterator[list[events.Event]]:
    seen: list[events.Event] = []
    events.subscribe("forecast.updated", seen.append)
    yield seen
    events.unsubscribe("forecast.updated", seen.append)


def synced_event(business_id: uuid.UUID) -> events.Event:
    return events.Event(name="transactions.synced", business_id=business_id, payload={})


def recompute(business_id: uuid.UUID) -> None:
    service.recompute_forecast(synced_event(business_id))


def snapshots(business_id: uuid.UUID) -> list[ForecastSnapshot]:
    with get_sessionmaker()() as session:
        found = list(
            session.scalars(
                select(ForecastSnapshot).where(
                    ForecastSnapshot.business_id == business_id
                )
            )
        )
        session.expunge_all()
    return found


def latest(business_id: uuid.UUID) -> ForecastSnapshot:
    with get_sessionmaker()() as session:
        found = repository.latest_snapshot(session, business_id=business_id)
        assert found is not None
        session.expunge_all()
    return found


def weeks_of(snapshot_id: uuid.UUID) -> list[ForecastWeek]:
    with get_sessionmaker()() as session:
        found = repository.snapshot_weeks(session, snapshot_id=snapshot_id)
        session.expunge_all()
    return found


def items_of(snapshot_id: uuid.UUID) -> list[ForecastItem]:
    with get_sessionmaker()() as session:
        found = repository.snapshot_items(session, snapshot_id=snapshot_id)
        session.expunge_all()
    return found


def business_with(accounts: list[PlaidAccount]) -> Connected:
    _, business_id = _owner({**HARBOR, "name": f"Forecast {uuid.uuid4().hex[:6]}"})
    return make_connection(business_id, accounts)


def synced_cash() -> tuple[Cash, PlaidAccount]:
    """`cash_business()` after one sync, which stores a forecast.

    The sync brings a monthly rent (a pattern) and one client deposit (an estimate).
    """
    cash = cash_business()
    key = uuid.uuid4().hex[:8]
    rows = [
        *rent(cash.plaid_operating, key=f"rent-{key}-"),
        tx(f"deposit-{key}", cash.plaid_operating, -1500.0, day=date(2026, 9, 20)),
    ]
    fake = SyncFake()
    fake.script = [page([cash.plaid_operating], added=rows)]
    sync(fake, cash.connection)
    return cash, cash.plaid_operating


def plant_payment(
    cash: Cash,
    day: date,
    cents: int = -100_000,
    *,
    account_id: uuid.UUID | None = None,
    repeats: str | None = None,
    description: str = "Planted payment",
    matched_on: tuple[date, ...] = (),
) -> uuid.UUID:
    """A payment written straight to the table: no event, no rematch."""
    payment = ExpectedPayment(
        business_id=uuid.UUID(cash.business_id),
        account_id=account_id or cash.operating,
        description=description,
        amount_cents=cents,
        currency="CAD",
        date=day,
        repeats=repeats,
    )
    with get_sessionmaker()() as session:
        session.add(payment)
        session.flush()
        for occurrence in matched_on:
            session.add(
                ExpectedPaymentMatch(
                    expected_payment_id=payment.id,
                    occurrence_date=occurrence,
                    business_id=payment.business_id,
                    transaction_id=uuid.uuid4(),
                )
            )
        session.commit()
        return payment.id


def plant_pattern(business_id: uuid.UUID, account_id: uuid.UUID) -> uuid.UUID:
    row = RecurringPattern(
        business_id=business_id,
        account_id=account_id,
        counterparty="Ghost Ltd",
        description="Ghost rent",
        schedule="monthly",
        amount_cents=-50_000,
        currency="CAD",
        next_date=date(2026, 10, 15),
        confidence=80,
        transaction_ids=[],
    )
    with get_sessionmaker()() as session:
        session.add(row)
        session.commit()
        return row.id


def daily(account: PlaidAccount, days: int, key: str) -> list[PlaidTransaction]:
    return [
        tx(
            f"{key}{n}",
            account,
            -250.0 if n % 3 else 400.0,
            day=TODAY - timedelta(days=n),
            name=f"Client {n % 7}",
        )
        for n in range(1, days + 1)
    ]


# S1


def test_stores_thirteen_weeks(updates: list[events.Event]) -> None:
    """C1."""
    cash, _ = synced_cash()
    bid = uuid.UUID(cash.business_id)
    stored = snapshots(bid)
    assert len(stored) == 1
    weeks = weeks_of(stored[0].id)
    assert [w.number for w in weeks] == list(range(1, 14))
    assert [w.starts_on for w in weeks] == MONDAYS
    assert stored[0].as_of == TODAY


def test_opening_balance() -> None:
    """C2."""
    accounts = [
        plaid_account("Checking", current=1000.0),
        plaid_account("Savings", subtype="savings", current=500.0),
        plaid_account("Null savings", subtype="savings", current=None),
        plaid_account("Excluded checking", current=700.0),
        plaid_account("Card", type="credit", subtype="credit card", current=90.0),
        plaid_account("Line", type="credit", subtype="line of credit", current=300.0),
        plaid_account("US checking", current=400.0, iso="USD"),
    ]
    c = business_with(accounts)
    with get_sessionmaker()() as session:
        rows = {
            r.name: r
            for r in session.scalars(
                select(BankAccount).where(BankAccount.business_id == c.business_id)
            )
        }
        rows["Savings"].included = True
        rows["Null savings"].included = True
        rows["Excluded checking"].included = False
        session.commit()
    recompute(c.business_id)
    assert latest(c.business_id).opening_balance_cents == 150_000


@pytest.mark.parametrize("days", [0, 14, 730])
def test_done_when_history_lengths(days: int) -> None:
    """C6: sync, then the handlers, then GET .../forecast."""
    account = plaid_account("Operating", current=8000.0)
    c = business_with_owner([account])
    fake = SyncFake()
    moved = dataclasses.replace(account, current=8100.0)
    fake.script = [page([moved], added=daily(account, days, f"d{days}-"))]
    sync(fake, c)
    caller_headers = owner_headers(c.business_id)
    response = client.get(
        f"/v1/businesses/{c.business_id}/forecast", headers=caller_headers
    )
    assert response.status_code == 200, response.text
    assert [w["number"] for w in response.json()["weeks"]] == list(range(1, 14))


_owners: dict[uuid.UUID, dict[str, str]] = {}


def business_with_owner(accounts: list[PlaidAccount]) -> Connected:
    caller, business_id = _owner({**HARBOR, "name": f"Forecast {uuid.uuid4().hex[:6]}"})
    c = make_connection(business_id, accounts)
    _owners[c.business_id] = caller.headers
    return c


def owner_headers(business_id: uuid.UUID) -> dict[str, str]:
    return _owners[business_id]


class Raising:
    name = "recurring_pattern"

    def forecast(self, inputs: strategies.ForecastInputs) -> strategies.ForecastResult:
        raise RuntimeError("boom")


class TwelveWeeks:
    name = "recurring_pattern"

    def forecast(self, inputs: strategies.ForecastInputs) -> strategies.ForecastResult:
        result = strategies.RecurringPatternStrategy().forecast(inputs)
        return dataclasses.replace(result, weeks=result.weeks[:12])


@pytest.mark.parametrize(
    ("broken", "error_type"),
    [(Raising(), "RuntimeError"), (TwelveWeeks(), "StrategyWeekCountError")],
)
def test_strategy_fallback(
    broken: Any,
    error_type: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C8."""
    cash = cash_business()
    bid = uuid.UUID(cash.business_id)
    plant_payment(cash, date(2026, 10, 20))
    monkeypatch.setitem(strategies.STRATEGIES, "recurring_pattern", broken)
    configure_logging()
    capsys.readouterr()
    recompute(bid)
    out = capsys.readouterr().out

    stored = latest(bid)
    assert stored.strategy == "rolling_average"
    with get_sessionmaker()() as session:
        given = service.forecast_inputs(session, business_id=bid, now=NOW)
    expected = strategies.STRATEGIES["rolling_average"].forecast(given)
    assert [
        (w.end_balance_cents, w.low_cents, w.high_cents) for w in weeks_of(stored.id)
    ] == [(w.end_balance_cents, w.low_cents, w.high_cents) for w in expected.weeks]
    failed = [x for x in log_lines(out) if x["event"] == "forecast.strategy_failed"]
    assert len(failed) == 1
    assert failed[0]["business_id"] == str(bid)
    assert failed[0]["strategy"] == "recurring_pattern"
    assert failed[0]["error_type"] == error_type


def test_strategy_setting_selects(monkeypatch: pytest.MonkeyPatch) -> None:
    """C10."""
    assert set(strategies.STRATEGIES) == {"recurring_pattern", "rolling_average"}
    for key, strategy in strategies.STRATEGIES.items():
        assert strategy.name == key
        assert callable(strategy.forecast)

    cash = cash_business()
    plant_payment(cash, date(2026, 10, 20))
    monkeypatch.setenv("FORECAST_STRATEGY", "rolling_average")
    get_settings.cache_clear()
    try:
        recompute(uuid.UUID(cash.business_id))
    finally:
        monkeypatch.delenv("FORECAST_STRATEGY")
        get_settings.cache_clear()
    assert latest(uuid.UUID(cash.business_id)).strategy == "rolling_average"


# S2


def test_pattern_account_not_cash() -> None:
    """C14: patterns on an excluded and on a USD account give no items."""
    accounts = [
        plaid_account("Operating", current=1000.0),
        plaid_account("Excluded checking", current=700.0),
        plaid_account("US checking", current=400.0, iso="USD"),
    ]
    c = business_with(accounts)
    with get_sessionmaker()() as session:
        rows = {
            r.name: r
            for r in session.scalars(
                select(BankAccount).where(BankAccount.business_id == c.business_id)
            )
        }
        rows["Excluded checking"].included = False
        session.commit()
        ids = {name: r.id for name, r in rows.items()}
    excluded = plant_pattern(c.business_id, ids["Excluded checking"])
    usd = plant_pattern(c.business_id, ids["US checking"])
    included = plant_pattern(c.business_id, ids["Operating"])
    recompute(c.business_id)
    sources = {i.source_id for i in items_of(latest(c.business_id).id)}
    assert included in sources
    assert not {excluded, usd} & sources


def test_expected_items() -> None:
    """C15."""
    cash = cash_business()
    bid = uuid.UUID(cash.business_id)
    monthly = plant_payment(
        cash, date(2026, 10, 20), 250_000, repeats="monthly", description="Retainer"
    )
    overdue = plant_payment(cash, date(2026, 9, 1), description="Old invoice")
    matched = plant_payment(cash, date(2026, 9, 20), matched_on=(date(2026, 9, 20),))
    on_card = plant_payment(cash, date(2026, 10, 10), account_id=cash.visa)
    recompute(bid)
    items = [i for i in items_of(latest(bid).id) if i.source == "expected_payment"]

    first = next(i for i in items if i.source_id == monthly)
    assert (first.date, first.amount_cents, first.description, first.schedule) == (
        date(2026, 10, 20),
        250_000,
        "Retainer",
        "monthly",
    )
    assert first.account_id == cash.operating
    assert [i.date for i in items if i.source_id == overdue] == [TODAY]
    assert [i for i in items if i.source_id in (matched, on_card)] == []


# S4


def test_subscriptions_order() -> None:
    """C26. Spec 24 appends the alert handlers after these (its C29)."""
    assert subscriptions.SUBSCRIPTIONS[:4] == (
        ("transactions.synced", service.refresh_recurring_patterns),
        ("transactions.synced", service.match_expected_payments),
        ("transactions.synced", service.recompute_forecast),
        ("forecast_inputs.changed", service.recompute_forecast),
    )


def test_same_event_twice(updates: list[events.Event]) -> None:
    """C27: the sync's event, handled again through the bus."""
    seen: list[events.Event] = []
    events.subscribe("transactions.synced", seen.append)
    try:
        cash, _ = synced_cash()
    finally:
        events.unsubscribe("transactions.synced", seen.append)
    bid = uuid.UUID(cash.business_id)
    assert len(seen) == 1
    events.publish(seen[0])
    assert len(snapshots(bid)) == 1
    assert [u.business_id for u in updates] == [bid]


def test_inputs_revert(updates: list[events.Event]) -> None:
    """C28."""
    cash, _ = synced_cash()
    bid = uuid.UUID(cash.business_id)
    first = latest(bid).id
    with get_sessionmaker()() as session:
        created = service.save_expected_payment(
            session,
            business_id=bid,
            user_id=cash.caller.id,
            payment_id=None,
            account_id=None,
            description="Acme Co, invoice 1042",
            amount_cents=800_000,
            day=date(2026, 10, 6),
            repeats=None,
            now=NOW,
        )
    assert latest(bid).id != first
    with get_sessionmaker()() as session:
        service.delete_expected_payment(
            session, business_id=bid, user_id=cash.caller.id, payment_id=created.id
        )
    assert latest(bid).id == first
    assert len(snapshots(bid)) == 2
    assert len(updates) == 3
    assert dict(updates[-1].payload) == {"snapshot_id": str(first)}


def test_concurrent_recomputes(
    monkeypatch: pytest.MonkeyPatch, updates: list[events.Event]
) -> None:
    """C29: the first sleeps 1 second inside the lock; the second writes after it."""
    cash, _ = synced_cash()
    bid = uuid.UUID(cash.business_id)
    plant_payment(cash, date(2026, 10, 20))
    clocks = {"first": NOW, "second": NOW + timedelta(days=1)}
    monkeypatch.setattr(
        service, "clock", lambda: clocks[threading.current_thread().name]
    )
    real_fingerprint = engine.fingerprint
    real_upsert = repository.upsert_snapshot
    marks: dict[str, float] = {}

    def slow_fingerprint(*args: Any, **kwargs: Any) -> str:
        if threading.current_thread().name == "first":
            marks["first_locked"] = time.monotonic()
            time.sleep(1)
        return real_fingerprint(*args, **kwargs)

    def timed_upsert(*args: Any, **kwargs: Any) -> tuple[uuid.UUID, bool]:
        marks[f"{threading.current_thread().name}_write"] = time.monotonic()
        return real_upsert(*args, **kwargs)

    monkeypatch.setattr(engine, "fingerprint", slow_fingerprint)
    monkeypatch.setattr(repository, "upsert_snapshot", timed_upsert)
    errors: list[BaseException] = []

    def run(delay: float) -> None:
        time.sleep(delay)
        try:
            recompute(bid)
        except BaseException as exc:  # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [
        threading.Thread(target=run, args=(0,), name="first"),
        threading.Thread(target=run, args=(0.2,), name="second"),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert errors == []
    assert marks["second_write"] - marks["first_locked"] >= 1.0
    assert marks["second_write"] > marks["first_write"]
    stored = snapshots(bid)
    assert len(stored) == 3
    assert len({s.inputs_sha256 for s in stored}) == 3

    # Same inputs at the same moment: one row for the fingerprint, one update.
    plant_payment(cash, date(2026, 11, 20))
    clocks["second"] = NOW
    before = len(updates)
    threads = [
        threading.Thread(target=run, args=(0,), name="first"),
        threading.Thread(target=run, args=(0.2,), name="second"),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(20)
    assert errors == []
    assert len(snapshots(bid)) == 4
    assert len(updates) == before + 1


def test_updated_event_after_commit() -> None:
    """C30: the handler sees the row from a fresh session."""
    seen: list[tuple[events.Event, ForecastSnapshot | None]] = []

    def record(event: events.Event) -> None:
        with get_sessionmaker()() as session:
            row = repository.latest_snapshot(session, business_id=event.business_id)
            session.expunge_all()
        seen.append((event, row))

    events.subscribe("forecast.updated", record)
    try:
        cash, _ = synced_cash()
    finally:
        events.unsubscribe("forecast.updated", record)
    bid = uuid.UUID(cash.business_id)
    assert len(seen) == 1
    event, row = seen[0]
    assert event.name == "forecast.updated"
    assert event.business_id == bid
    assert row is not None
    assert dict(event.payload) == {"snapshot_id": str(row.id)}
    assert row.id == latest(bid).id


def test_failure_keeps_latest(
    monkeypatch: pytest.MonkeyPatch,
    updates: list[events.Event],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C30: a strategy and a fallback that both raise."""
    cash, _ = synced_cash()
    bid = uuid.UUID(cash.business_id)
    before = latest(bid).id
    count = len(snapshots(bid))
    published = len(updates)
    plant_payment(cash, date(2026, 10, 20))

    class AlsoRaising(Raising):
        name = "rolling_average"

    monkeypatch.setitem(strategies.STRATEGIES, "recurring_pattern", Raising())
    monkeypatch.setitem(strategies.STRATEGIES, "rolling_average", AlsoRaising())
    configure_logging()
    capsys.readouterr()
    events.publish(
        events.Event(
            name="forecast_inputs.changed",
            business_id=bid,
            payload={"source": "expected_payments", "expected_payment_id": "x"},
        )
    )
    out = capsys.readouterr().out
    assert latest(bid).id == before
    assert len(snapshots(bid)) == count
    assert len(updates) == published
    failed = [x for x in log_lines(out) if x["event"] == "event.handler_failed"]
    assert [x["handler"] for x in failed] == ["recompute_forecast"]


def test_logged_without_amounts(capsys: pytest.CaptureFixture[str]) -> None:
    """C35."""
    cash = cash_business()
    bid = uuid.UUID(cash.business_id)
    plant_payment(cash, date(2026, 10, 20), -123_457, description="Secret Supplier")
    configure_logging()
    capsys.readouterr()
    recompute(bid)
    recompute(bid)
    out = capsys.readouterr().out
    lines = log_lines(out)
    written = [x for x in lines if x["event"] == "forecast.updated"]
    assert len(written) == 1
    standard = {"event", "level", "timestamp", "logger"}
    assert set(written[0]) - standard == {
        "business_id",
        "snapshot_id",
        "strategy",
        "items",
        "duration_ms",
    }
    assert written[0]["business_id"] == str(bid)
    assert written[0]["snapshot_id"] == str(latest(bid).id)
    assert written[0]["items"] == len(items_of(latest(bid).id))
    unchanged = [x for x in lines if x["event"] == "forecast.unchanged"]
    assert len(unchanged) == 1
    assert set(unchanged[0]) - standard == {"business_id"}
    for secret in ("123457", "Secret Supplier", "Visa", "Operating"):
        assert secret not in out
