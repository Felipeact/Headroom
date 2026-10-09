"""Spec 23: GET and PUT .../minimum-balance (AD-087, AD-088, AD-089)."""

import uuid
from collections.abc import Iterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import events
from app.audit import AuditLog
from app.db import get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.forecasting.models import MinimumBalance
from tests.test_businesses import Caller
from tests.test_expected_payments_api import Cash, cash_business, is_problem
from tests.test_forecast_recompute import (
    _registered_and_clock,  # noqa: F401 - autouse: handlers subscribed, clocks fixed
    latest,
    snapshots,
    synced_cash,
)
from tests.test_recurring_refresh import log_lines
from tests.test_transaction_sync import (
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

KEYS = {"amount_cents", "currency", "suggested_cents", "updated_at"}


def path(business_id: str | uuid.UUID, route: str = "minimum-balance") -> str:
    return f"/v1/businesses/{business_id}/{route}"


def get(cash: Cash) -> Any:
    response = client.get(path(cash.business_id), headers=cash.caller.headers)
    assert response.status_code == 200, response.text
    return response.json()


def put(cash: Cash, body: Any) -> Any:
    return client.put(path(cash.business_id), json=body, headers=cash.caller.headers)


def stored(business_id: str) -> list[MinimumBalance]:
    with get_sessionmaker()() as session:
        found = list(
            session.scalars(
                select(MinimumBalance).where(
                    MinimumBalance.business_id == uuid.UUID(business_id)
                )
            )
        )
        session.expunge_all()
    return found


def audit_rows(business_id: str) -> list[AuditLog]:
    with get_sessionmaker()() as session:
        found = list(
            session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.business_id == uuid.UUID(business_id),
                    AuditLog.target_type == "minimum_balance",
                )
                .order_by(AuditLog.id)
            )
        )
        session.expunge_all()
    return found


@pytest.fixture
def changes() -> Iterator[list[tuple[events.Event, list[int]]]]:
    """Each `forecast_inputs.changed`, with the amounts a new session sees right then."""
    seen: list[tuple[events.Event, list[int]]] = []

    def record(event: events.Event) -> None:
        amounts = [r.amount_cents for r in stored(str(event.business_id))]
        seen.append((event, amounts))

    events.subscribe("forecast_inputs.changed", record)
    yield seen
    events.unsubscribe("forecast_inputs.changed", record)


def test_unset_shape() -> None:
    """C1."""
    body = get(cash_business())
    assert set(body) == KEYS
    assert body["amount_cents"] is None
    assert body["updated_at"] is None
    assert body["currency"] == "CAD"


def test_put_then_get() -> None:
    """C2."""
    cash = cash_business()
    response = put(cash, {"amount_cents": 500_000})
    assert response.status_code == 200, response.text
    assert set(response.json()) == KEYS
    assert response.json()["amount_cents"] == 500_000
    assert response.json()["updated_at"] is not None
    datetime.fromisoformat(response.json()["updated_at"])
    assert get(cash)["amount_cents"] == 500_000

    response = put(cash, {"amount_cents": 250_000})
    assert response.status_code == 200
    assert response.json()["amount_cents"] == 250_000
    assert get(cash)["amount_cents"] == 250_000
    assert [r.amount_cents for r in stored(cash.business_id)] == [250_000]


def test_body_bounds() -> None:
    """C7."""
    cash = cash_business()
    assert put(cash, {"amount_cents": 0}).status_code == 200
    assert put(cash, {"amount_cents": 1_000_000_000}).status_code == 200
    for body in (
        {"amount_cents": -1},
        {"amount_cents": 1_000_000_001},
        {"amount_cents": 12.5},
        {"amount_cents": "5000"},
        {},
        {"amount_cents": None},
        {"amount_cents": 1, "currency": "USD"},
    ):
        is_problem(put(cash, body), 422)
    assert get(cash)["amount_cents"] == 1_000_000_000


def test_audit_and_event(changes: list[tuple[events.Event, list[int]]]) -> None:
    """C8."""
    cash = cash_business()
    assert put(cash, {"amount_cents": 500_000}).status_code == 200
    assert put(cash, {"amount_cents": 300_000}).status_code == 200

    rows = audit_rows(cash.business_id)
    assert [r.action for r in rows] == ["minimum_balance.changed"] * 2
    assert [r.details for r in rows] == [
        {"amount_cents": 500_000},
        {"amount_cents": 300_000},
    ]
    for row in rows:
        assert row.actor_user_id == str(cash.caller.id)

    assert [amounts for _, amounts in changes] == [[500_000], [300_000]]
    for event, _ in changes:
        assert event.name == "forecast_inputs.changed"
        assert event.business_id == uuid.UUID(cash.business_id)
        assert dict(event.payload) == {"source": "minimum_balance"}


def test_same_amount_quiet(changes: list[tuple[events.Event, list[int]]]) -> None:
    """C9."""
    cash = cash_business()
    assert put(cash, {"amount_cents": 500_000}).status_code == 200
    response = put(cash, {"amount_cents": 500_000})
    assert response.status_code == 200
    assert response.json()["amount_cents"] == 500_000
    assert len(audit_rows(cash.business_id)) == 1
    assert len(changes) == 1


def test_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """C10."""
    a = cash_business()
    b = cash_business()
    assert put(b, {"amount_cents": 700_000}).status_code == 200

    def calls(headers: dict[str, str], business_id: str) -> list[Any]:
        return [
            client.get(path(business_id), headers=headers),
            client.put(path(business_id), json={"amount_cents": 1}, headers=headers),
            client.get(path(business_id, "forecast/status"), headers=headers),
        ]

    for response in calls(Caller().headers, a.business_id) + calls(
        a.caller.headers, b.business_id
    ):
        is_problem(response, 404)
        assert response.json()["detail"] == "Business not found."
    for response in calls({}, a.business_id):
        is_problem(response, 401)

    monkeypatch.setattr(
        accounts_service,
        "get_membership",
        lambda *_, **__: SimpleNamespace(role="viewer"),
    )
    response = put(a, {"amount_cents": 1})
    is_problem(response, 403)
    assert response.json()["detail"] == "You don't have permission to do this."
    monkeypatch.undo()
    assert stored(a.business_id) == []
    assert [r.amount_cents for r in stored(b.business_id)] == [700_000]


def test_recompute_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    """C12."""
    cash, _ = synced_cash()
    bid = uuid.UUID(cash.business_id)
    before = latest(bid).id
    count = len(snapshots(bid))
    configure_logging()
    capsys.readouterr()
    assert put(cash, {"amount_cents": 500_000}).status_code == 200
    lines = log_lines(capsys.readouterr().out)
    unchanged = [x for x in lines if x["event"] == "forecast.unchanged"]
    assert [x["business_id"] for x in unchanged] == [str(bid)]
    assert latest(bid).id == before
    assert len(snapshots(bid)) == count


def test_one_row_per_business() -> None:
    """C2: repeated changes keep one row."""
    cash = cash_business()
    for amount in (1, 2, 3):
        assert put(cash, {"amount_cents": amount}).status_code == 200
    with get_sessionmaker()() as session:
        count = session.scalar(
            select(func.count())
            .select_from(MinimumBalance)
            .where(MinimumBalance.business_id == uuid.UUID(cash.business_id))
        )
    assert count == 1
