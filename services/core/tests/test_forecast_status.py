"""Spec 23: GET .../forecast/status (AD-090)."""

import dataclasses
import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, update

from app.db import get_sessionmaker
from app.main import app
from app.modules.bank_sync.models import BankAccount, BankConnection
from app.modules.forecasting.models import ForecastSnapshot, RecurringPattern
from tests.test_bank_connect import plaid_account
from tests.test_expected_payments_api import Cash, cash_business
from tests.test_forecast_recompute import (
    TODAY,
    _registered_and_clock,  # noqa: F401 - autouse: handlers subscribed, clocks fixed
    plant_payment,
    recompute,
    snapshots,
    synced_cash,
)
from tests.test_transaction_sync import (
    SyncFake,
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
    make_connection,
    page,
    sync,
    tx,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

KEYS = {
    "state",
    "institution_names",
    "transactions_read",
    "history_months",
    "recurring_count",
    "recurring_names",
}


def status(cash: Cash) -> Any:
    response = client.get(
        f"/v1/businesses/{cash.business_id}/forecast/status",
        headers=cash.caller.headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def set_connection(connection_id: uuid.UUID, **values: Any) -> None:
    with get_sessionmaker()() as session:
        session.execute(
            update(BankConnection)
            .where(BankConnection.id == connection_id)
            .values(**values)
        )
        session.commit()


def sync_rows(cash: Cash, rows: list[Any]) -> None:
    fake = SyncFake()
    fake.script = [page([cash.plaid_operating], added=rows)]
    sync(fake, cash.connection)


def plant_patterns(business_id: str, rows: list[tuple[str, str, int]]) -> None:
    """Patterns written straight to the table: (counterparty, description, amount)."""
    with get_sessionmaker()() as session:
        for counterparty, description, amount in rows:
            session.add(
                RecurringPattern(
                    business_id=uuid.UUID(business_id),
                    account_id=uuid.uuid4(),
                    counterparty=counterparty,
                    description=description,
                    schedule="monthly",
                    amount_cents=amount,
                    currency="CAD",
                    next_date=date(2026, 10, 15),
                    confidence=80,
                    transaction_ids=[],
                )
            )
        session.commit()


def test_shape() -> None:
    """C13."""
    assert set(status(cash_business())) == KEYS


def test_never_synced_building() -> None:
    """C14."""
    cash = cash_business()
    body = status(cash)
    assert body["state"] == "building"
    assert body["transactions_read"] is False

    response = client.put(
        f"/v1/businesses/{cash.business_id}/minimum-balance",
        json={"amount_cents": 500_000},
        headers=cash.caller.headers,
    )
    assert response.status_code == 200
    assert len(snapshots(uuid.UUID(cash.business_id))) == 1
    body = status(cash)
    assert body["state"] == "building"
    assert body["transactions_read"] is False


def test_synced_ready() -> None:
    """C15."""
    cash, _ = synced_cash()
    body = status(cash)
    assert body["state"] == "ready"
    assert body["transactions_read"] is True


def test_stale_fingerprint_building() -> None:
    """C16."""
    cash, _ = synced_cash()
    bid = uuid.UUID(cash.business_id)
    with get_sessionmaker()() as session:
        session.execute(
            delete(ForecastSnapshot).where(ForecastSnapshot.business_id == bid)
        )
        session.commit()
    assert status(cash)["state"] == "building"

    recompute(bid)
    assert status(cash)["state"] == "ready"
    plant_payment(cash, TODAY + timedelta(days=10), -42_000)
    assert status(cash)["state"] == "building"
    recompute(bid)
    assert status(cash)["state"] == "ready"


def test_minimum_before_sync() -> None:
    """C17."""
    cash = cash_business()
    response = client.put(
        f"/v1/businesses/{cash.business_id}/minimum-balance",
        json={"amount_cents": 500_000},
        headers=cash.caller.headers,
    )
    assert response.status_code == 200
    assert status(cash)["state"] == "building"
    sync_rows(cash, [tx("first", cash.plaid_operating, 120.0, day=date(2026, 9, 20))])
    assert status(cash)["state"] == "ready"


def test_needs_attention() -> None:
    """C18."""
    cash, _ = synced_cash()
    assert status(cash)["state"] == "ready"
    set_connection(cash.connection.connection_id, login_required=True)
    assert status(cash)["state"] == "needs_attention"

    other, _ = synced_cash()
    card_only = make_connection(other.business_id, [])
    set_connection(card_only.connection_id, login_required=True)
    assert status(other)["state"] == "ready"


def test_details() -> None:
    """C19."""
    cash = cash_business()
    second = make_connection(cash.business_id, [])
    set_connection(cash.connection.connection_id, institution_name="Bank A")
    set_connection(second.connection_id, institution_name="Bank B")
    body = status(cash)
    assert body["institution_names"] == ["Bank A", "Bank B"]
    assert body["history_months"] is None
    assert body["recurring_count"] == 0
    assert body["recurring_names"] == []

    plant_patterns(cash.business_id, [("Payroll Co", "Payroll", -900_000)])
    body = status(cash)
    assert body["recurring_count"] == 1
    assert body["recurring_names"] == ["Payroll Co"]

    plant_patterns(
        cash.business_id,
        [
            ("", "Rent", -300_000),
            ("Hydro One", "Hydro", -20_000),
            ("Client", "Deposit", 250_000),
        ],
    )
    body = status(cash)
    assert body["recurring_count"] == 4
    assert body["recurring_names"] == ["Payroll Co", "Rent"]


@pytest.mark.parametrize(
    ("oldest", "months"),
    [
        (date(2026, 9, 1), 0),
        (date(2026, 6, 26), 3),
        (date(2026, 6, 27), 2),
        (date(2024, 9, 26), 24),
    ],
)
def test_details_history_months(oldest: date, months: int) -> None:
    """C19: whole months from the oldest included-account transaction to today."""
    cash = cash_business()
    sync_rows(
        cash,
        [
            tx("old", cash.plaid_operating, 50.0, day=oldest),
            tx("new", cash.plaid_operating, 60.0, day=date(2026, 9, 20)),
        ],
    )
    assert status(cash)["history_months"] == months


def test_details_excluded_account_not_counted() -> None:
    """C19: a transaction only on the excluded Visa leaves `history_months` null."""
    cash = cash_business()
    with get_sessionmaker()() as session:
        visa_row = session.get(BankAccount, cash.visa)
        assert visa_row is not None
        visa = dataclasses.replace(
            plaid_account("Visa", type="credit", subtype="credit card", mask="5530"),
            account_id=visa_row.provider_account_id,
        )
    fake = SyncFake()
    fake.script = [
        page(
            [cash.plaid_operating, visa],
            added=[tx("card", visa, 30.0, day=date(2025, 1, 5))],
        )
    ]
    sync(fake, cash.connection)
    assert status(cash)["history_months"] is None
