"""Spec 21 "Done when" 3: a forecast for 2 years of history takes under 2 seconds."""

import random
import time
import uuid
from datetime import date, timedelta

import pytest

from app.db import get_sessionmaker
from app.modules.bank_sync.service import is_business_day
from app.modules.forecasting import repository
from app.modules.forecasting.models import RecurringPattern
from tests.test_expected_payments_api import cash_business
from tests.test_forecast_recompute import (
    TODAY,
    _registered_and_clock,  # noqa: F401 - autouse: handlers subscribed, clocks fixed
    plant_payment,
    recompute,
)
from tests.test_transaction_sync import (
    SyncFake,
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
    page,
    sync,
    tx,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

PER_BUSINESS_DAY = 20
LIMIT_SECONDS = 2.0


def test_two_years_under_two_seconds() -> None:
    """C41: one timed run, from the handler's start to its commit."""
    cash = cash_business()
    bid = uuid.UUID(cash.business_id)
    rng = random.Random(21)
    days = [
        TODAY - timedelta(days=n)
        for n in range(1, 731)
        if is_business_day(TODAY - timedelta(days=n))
    ]
    accounts = (cash.plaid_operating,)
    rows = [
        tx(
            f"perf{d.isoformat()}-{k}",
            accounts[0],
            rng.choice([-1, 1]) * rng.randint(100, 500_000) / 100,
            day=d,
            name=f"Counterparty {rng.randint(1, 400)}",
        )
        for d in days
        for k in range(PER_BUSINESS_DAY)
    ]
    fake = SyncFake()
    fake.script = [page(list(accounts), added=rows)]
    sync(fake, cash.connection)

    with get_sessionmaker()() as session:
        session.add_all(
            RecurringPattern(
                business_id=bid,
                account_id=cash.operating,
                counterparty=name,
                description=name,
                schedule="monthly",
                amount_cents=cents,
                currency="CAD",
                next_date=date(2026, 10, day),
                confidence=90,
                transaction_ids=[],
            )
            for name, cents, day in (
                ("Payroll", -1_120_000, 2),
                ("Rent", -380_000, 15),
                ("Software", -64_000, 7),
            )
        )
        session.commit()
    for n in range(4):
        plant_payment(cash, date(2026, 10, 6) + timedelta(weeks=3 * n), 100_000 + n)
    with get_sessionmaker()() as session:
        assert len(repository.patterns(session, business_id=bid)) >= 3
        before = repository.latest_snapshot(session, business_id=bid)
        assert before is not None

    started = time.perf_counter()
    recompute(bid)
    elapsed = time.perf_counter() - started

    with get_sessionmaker()() as session:
        after = repository.latest_snapshot(session, business_id=bid)
    assert after is not None and after.id != before.id, "the timed run must write"
    assert len(rows) >= 20 * 500
    assert elapsed < LIMIT_SECONDS, f"{elapsed:.2f}s"
