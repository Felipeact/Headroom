"""Spec 21: GET .../forecast and GET .../upcoming (AD-080)."""

import uuid
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.db import get_sessionmaker
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync.models import BankConnection
from app.modules.forecasting.api import get_now
from tests.test_bank_connect import plaid_account
from tests.test_expected_payments_api import Cash, cash_business, is_problem
from tests.test_forecast_recompute import (
    NOW,
    TODAY,
    _registered_and_clock,  # noqa: F401 - autouse: handlers subscribed, clocks fixed
    plant_payment,
    recompute,
    synced_cash,
)
from tests.test_transaction_sync import (
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
    make_connection,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

FORECAST_KEYS = {
    "id",
    "as_of",
    "computed_at",
    "strategy",
    "currency",
    "opening_balance_cents",
    "incomplete",
    "weeks",
    "items",
}
WEEK_KEYS = {
    "number",
    "starts_on",
    "ends_on",
    "end_balance_cents",
    "low_cents",
    "high_cents",
    "money_in_cents",
    "money_out_cents",
    "item_ids",
}
ITEM_KEYS = {
    "id",
    "date",
    "account_id",
    "amount_cents",
    "currency",
    "source",
    "source_id",
    "description",
    "counterparty",
    "schedule",
}


@pytest.fixture
def request_clock() -> Iterator[list[datetime]]:
    now = [NOW]
    app.dependency_overrides[get_now] = lambda: now[0]
    yield now
    app.dependency_overrides[get_now] = lambda: NOW


def path(business_id: str | uuid.UUID, route: str = "forecast") -> str:
    return f"/v1/businesses/{business_id}/{route}"


def get(cash: Cash, route: str = "forecast") -> Any:
    response = client.get(path(cash.business_id, route), headers=cash.caller.headers)
    assert response.status_code == 200, response.text
    return response.json()


def order_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (item["date"], item["source"], item["id"])


def forecast_business() -> Cash:
    """A synced business with planted payments around the next 14 days."""
    cash, _ = synced_cash()
    for offset in (0, 3, 13, 14, 40):
        plant_payment(cash, TODAY + timedelta(days=offset), -10_000 - offset)
    recompute(uuid.UUID(cash.business_id))
    return cash


def test_forecast_shape() -> None:
    """C36."""
    body = get(forecast_business())
    assert set(body) == FORECAST_KEYS
    assert body["as_of"] == "2026-09-26"
    assert body["currency"] == "CAD"
    assert body["strategy"] == "recurring_pattern"
    assert [w["number"] for w in body["weeks"]] == list(range(1, 14))
    for w in body["weeks"]:
        assert set(w) == WEEK_KEYS
        starts = date.fromisoformat(w["starts_on"])
        assert date.fromisoformat(w["ends_on"]) == starts + timedelta(days=6)
        assert w["money_out_cents"] <= 0
    assert body["items"]
    for item in body["items"]:
        assert set(item) == ITEM_KEYS
    assert body["items"] == sorted(body["items"], key=order_key)


def test_week_item_ids() -> None:
    """C4: each week's item IDs are exactly its items, by date, source, ID."""
    body = get(forecast_business())
    items = {i["id"]: i for i in body["items"]}
    as_of = date.fromisoformat(body["as_of"])
    listed: list[str] = []
    for w in body["weeks"]:
        first = as_of if w["number"] == 1 else date.fromisoformat(w["starts_on"])
        last = date.fromisoformat(w["ends_on"])
        holds = [
            i for i in body["items"] if first <= date.fromisoformat(i["date"]) <= last
        ]
        assert w["item_ids"] == [i["id"] for i in sorted(holds, key=order_key)]
        assert w["money_in_cents"] == sum(
            items[i]["amount_cents"]
            for i in w["item_ids"]
            if items[i]["amount_cents"] > 0
        )
        listed += w["item_ids"]
    assert sorted(listed) == sorted(items)


def test_not_ready() -> None:
    """C37."""
    cash = cash_business()
    for route in ("forecast", "upcoming"):
        response = client.get(
            path(cash.business_id, route), headers=cash.caller.headers
        )
        is_problem(response, 404)
        assert response.json()["detail"] == "Forecast not ready."


def set_connection(connection_id: uuid.UUID, **values: Any) -> None:
    with get_sessionmaker()() as session:
        session.execute(
            update(BankConnection)
            .where(BankConnection.id == connection_id)
            .values(**values)
        )
        session.commit()


def test_incomplete_cases(request_clock: list[datetime]) -> None:
    """C38."""
    cash, _ = synced_cash()
    connection = cash.connection.connection_id
    card_only = make_connection(
        cash.business_id,
        [plaid_account("Other card", type="credit", subtype="credit card")],
    )
    snapshot_id = get(cash)["id"]
    hours = timedelta(hours=1)
    cases: list[tuple[dict[str, Any], bool]] = [
        ({"last_synced_at": NOW - 47 * hours}, False),
        ({"last_synced_at": NOW - 48 * hours}, False),
        ({"last_synced_at": NOW - 48 * hours - timedelta(seconds=1)}, True),
        ({"last_synced_at": None}, True),
        ({"last_synced_at": NOW, "login_required": True}, True),
        ({"last_synced_at": NOW, "failed_nights": 3}, True),
    ]
    healthy = {"last_synced_at": NOW, "login_required": False, "failed_nights": 0}
    set_connection(card_only.connection_id, last_synced_at=NOW)
    for values, incomplete in cases:
        set_connection(connection, **{**healthy, **values})
        body = get(cash)
        assert body["incomplete"] is incomplete, values
        assert body["id"] == snapshot_id

    set_connection(connection, **healthy)
    set_connection(
        card_only.connection_id,
        login_required=True,
        failed_nights=3,
        last_synced_at=None,
    )
    assert get(cash)["incomplete"] is False

    set_connection(connection, last_synced_at=NOW - 47 * hours)
    assert get(cash)["incomplete"] is False
    request_clock[0] = NOW + 2 * hours
    body = get(cash)
    assert body["incomplete"] is True
    assert body["id"] == snapshot_id


def test_upcoming_range() -> None:
    """C39: payments planted today + 0, 3, 13, 14 and 40 days."""
    cash = forecast_business()
    forecast = get(cash)
    estimates = [
        i
        for i in forecast["items"]
        if i["source"] == "estimate" and i["date"] <= str(TODAY + timedelta(days=13))
    ]
    assert estimates, "the sample needs an estimate in range to prove it is left out"

    items = get(cash, "upcoming")["items"]
    expected = sorted(
        (
            i
            for i in forecast["items"]
            if i["source"] != "estimate"
            and str(TODAY) <= i["date"] <= str(TODAY + timedelta(days=13))
        ),
        key=order_key,
    )
    assert items == expected
    planted = {i["amount_cents"] for i in items if i["source"] == "expected_payment"}
    assert planted == {-10_000, -10_003, -10_013}
    for item in items:
        assert set(item) == ITEM_KEYS

    one = get(cash, "upcoming?days=1")["items"]
    assert [i["amount_cents"] for i in one if i["source"] == "expected_payment"] == [
        -10_000
    ]
    ninety = get(cash, "upcoming?days=90")["items"]
    assert -10_040 in {i["amount_cents"] for i in ninety}
    fourteen = get(cash, "upcoming?days=14")["items"]
    assert fourteen == items
    for bad in ("0", "91", "x"):
        response = client.get(
            path(cash.business_id, f"upcoming?days={bad}"), headers=cash.caller.headers
        )
        is_problem(response, 422)


def test_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """C42."""
    from tests.test_businesses import Caller

    a = forecast_business()
    b = forecast_business()
    b_forecast = get(b)
    for route in ("forecast", "upcoming"):
        for caller, business_id in (
            (Caller(), a.business_id),
            (a.caller, b.business_id),
        ):
            response = client.get(path(business_id, route), headers=caller.headers)
            is_problem(response, 404)
            assert response.json()["detail"] == "Business not found."
            assert b_forecast["id"] not in response.text
        is_problem(client.get(path("not-a-uuid", route), headers=a.caller.headers), 422)

    monkeypatch.setattr(
        accounts_service,
        "get_membership",
        lambda *_, **__: SimpleNamespace(role="bookkeeper"),
    )
    for route in ("forecast", "upcoming"):
        response = client.get(path(a.business_id, route), headers=a.caller.headers)
        is_problem(response, 403)
    monkeypatch.undo()
    assert get(a)["id"] != b_forecast["id"]
