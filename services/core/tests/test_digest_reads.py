"""Spec 30: the reads the weekly digest depends on (C32-C34), at their own layer."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import update

from app.db import get_sessionmaker
from app.modules.accounts import service as accounts_service
from app.modules.accounts.models import Business
from app.modules.forecasting import service as forecasting_service
from app.modules.forecasting.models import (
    ExpectedPayment,
    ExpectedPaymentMatch,
    ForecastPin,
    ForecastWeek,
)
from tests.test_expected_payments_api import owner_business
from tests.test_forecast_accuracy import plant_snapshot

pytestmark = pytest.mark.usefixtures("migrated_database")

MONDAY = date(2026, 10, 19)
NOW = datetime(2026, 10, 26, 12, tzinfo=UTC)


def new_business() -> uuid.UUID:
    return uuid.UUID(owner_business("Reads")[1])


def pin(business_id: uuid.UUID, snapshot_id: uuid.UUID, week_start: date) -> None:
    with get_sessionmaker()() as session:
        session.add(
            ForecastPin(
                business_id=business_id, week_start=week_start, snapshot_id=snapshot_id
            )
        )
        session.commit()


def test_pinned_forecast() -> None:
    """C32."""
    business_id = new_business()
    other = new_business()
    snapshot = plant_snapshot(business_id, MONDAY, base=1_000_000)
    pin(business_id, snapshot, MONDAY)
    pin(other, plant_snapshot(other, MONDAY, base=7_000_000), MONDAY)
    with get_sessionmaker()() as session:
        found = forecasting_service.pinned_forecast(
            session, business_id=business_id, week_start=MONDAY
        )
        assert found == forecasting_service.PinnedForecastView(
            opening_balance_cents=1_000_000,
            low_balance_cents=1_000_001,
            low_week_starts_on=MONDAY,
        )
        assert (
            forecasting_service.pinned_forecast(
                session, business_id=business_id, week_start=date(2026, 10, 12)
            )
            is None
        )
        assert (
            forecasting_service.pinned_forecast(
                session, business_id=new_business(), week_start=MONDAY
            )
            is None
        )
        # Another business's pin for the same Monday is never returned.
        theirs = forecasting_service.pinned_forecast(
            session, business_id=other, week_start=MONDAY
        )
        assert theirs is not None
        assert theirs.opening_balance_cents == 7_000_000


def test_pinned_forecast_low_ties_take_the_earlier_week() -> None:
    """C32: the tie rule."""
    business_id = new_business()
    snapshot = plant_snapshot(business_id, MONDAY, base=500)
    with get_sessionmaker()() as session:
        session.execute(
            update(ForecastWeek)
            .where(ForecastWeek.snapshot_id == snapshot, ForecastWeek.number == 6)
            .values(end_balance_cents=501)
        )
        session.commit()
    pin(business_id, snapshot, MONDAY)
    with get_sessionmaker()() as session:
        found = forecasting_service.pinned_forecast(
            session, business_id=business_id, week_start=MONDAY
        )
    assert found is not None
    assert found.low_balance_cents == 501
    assert found.low_week_starts_on == MONDAY


def payment(
    business_id: uuid.UUID,
    description: str,
    amount: int,
    created_at: datetime,
    *,
    day: date = date(2026, 11, 2),
) -> uuid.UUID:
    row = ExpectedPayment(
        business_id=business_id,
        account_id=uuid.uuid4(),
        description=description,
        amount_cents=amount,
        currency="CAD",
        date=day,
        repeats=None,
        created_at=created_at,
        updated_at=created_at,
    )
    with get_sessionmaker()() as session:
        session.add(row)
        session.commit()
        return row.id


def test_payments_added_since() -> None:
    """C33."""
    business_id = new_business()
    other = new_business()
    since = datetime(2026, 10, 19, 4, tzinfo=UTC)
    payment(business_id, "Small", -100_000, since)
    payment(business_id, "Large", 800_000, since + timedelta(days=3))
    payment(business_id, "Early", 900_000, since - timedelta(seconds=1))
    matched = payment(business_id, "Matched", 700_000, since, day=date(2026, 10, 20))
    payment(other, "Foreign", 5_000_000, since)
    with get_sessionmaker()() as session:
        session.add(
            ExpectedPaymentMatch(
                expected_payment_id=matched,
                business_id=business_id,
                occurrence_date=date(2026, 10, 20),
                transaction_id=uuid.uuid4(),
            )
        )
        session.commit()
    with get_sessionmaker()() as session:
        found = forecasting_service.expected_payments_added_since(
            session, business_id=business_id, since=since, now=NOW
        )
    assert found == [
        forecasting_service.AddedPaymentView(
            description="Large",
            amount_cents=800_000,
            currency="CAD",
            next_date=date(2026, 11, 2),
        ),
        forecasting_service.AddedPaymentView(
            description="Small",
            amount_cents=100_000,
            currency="CAD",
            next_date=date(2026, 11, 2),
        ),
    ]


def test_all_business_zones() -> None:
    """C34."""
    first = new_business()
    second = new_business()
    with get_sessionmaker()() as session:
        session.execute(
            update(Business)
            .where(Business.id == second)
            .values(time_zone="America/St_Johns")
        )
        session.execute(
            update(Business)
            .where(Business.id == first)
            .values(time_zone="America/Vancouver")
        )
        session.commit()
    with get_sessionmaker()() as session:
        zones = accounts_service.all_business_zones(session)
    assert zones[first] == "America/Vancouver"
    assert zones[second] == "America/St_Johns"
