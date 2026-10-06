"""Spec 19: `GET /v1/businesses/{business_id}/recurring-patterns` (AD-072)."""

import uuid
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db import get_sessionmaker
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.forecasting.models import RecurringPattern
from tests.test_businesses import HARBOR, Caller, _owner

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

ITEM_KEYS = {
    "id",
    "account_id",
    "counterparty",
    "description",
    "schedule",
    "amount_cents",
    "currency",
    "next_date",
    "confidence",
    "transaction_ids",
}


def path(business_id: str | uuid.UUID) -> str:
    return f"/v1/businesses/{business_id}/recurring-patterns"


def get(caller: Caller, business_id: str | uuid.UUID) -> Any:
    return client.get(path(business_id), headers=caller.headers)


def owner_business() -> tuple[Caller, str]:
    return _owner({**HARBOR, "name": f"Patterns {uuid.uuid4().hex[:6]}"})


def store(
    business_id: str, counterparty: str, schedule: str, next_date: date
) -> uuid.UUID:
    pattern = RecurringPattern(
        business_id=uuid.UUID(business_id),
        account_id=uuid.uuid4(),
        counterparty=counterparty,
        description=f"{counterparty} payment",
        schedule=schedule,
        amount_cents=-64_000,
        currency="CAD",
        next_date=next_date,
        confidence=83,
        transaction_ids=[uuid.uuid4(), uuid.uuid4()],
    )
    with get_sessionmaker()() as session:
        session.add(pattern)
        session.commit()
        return pattern.id


def test_order_and_shape() -> None:
    """C28."""
    caller, business_id = owner_business()
    weekly = store(business_id, "Bayline", "weekly", date(2026, 10, 7))
    zed = store(business_id, "Zed", "monthly", date(2026, 10, 2))
    acme = store(business_id, "Acme", "monthly", date(2026, 10, 2))

    response = get(caller, business_id)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items"}
    items = body["items"]
    assert [i["id"] for i in items] == [str(acme), str(zed), str(weekly)]
    for item in items:
        assert set(item) == ITEM_KEYS
        assert date.fromisoformat(item["next_date"])
        assert type(item["confidence"]) is int
        assert len(item["transaction_ids"]) == 2
    assert items[2]["schedule"] == "weekly"
    assert items[0]["amount_cents"] == -64_000


def test_empty_business() -> None:
    """C29."""
    caller, business_id = owner_business()
    response = get(caller, business_id)
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """C30."""
    caller, business_a = owner_business()
    _, business_b = owner_business()
    mine = store(business_a, "Mine", "monthly", date(2026, 10, 2))
    store(business_b, "Theirs", "monthly", date(2026, 10, 2))

    not_member = get(Caller(), business_a)
    assert not_member.status_code == 404
    assert not_member.json()["detail"] == "Business not found."
    assert get(caller, business_b).status_code == 404

    items = get(caller, business_a).json()["items"]
    assert [i["id"] for i in items] == [str(mine)]

    monkeypatch.setattr(
        accounts_service,
        "get_membership",
        lambda *_, **__: SimpleNamespace(role="viewer"),
    )
    forbidden = get(caller, business_a)
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "You don't have permission to do this."


def test_invalid_business_id() -> None:
    """C31."""
    response = get(Caller(), "not-a-uuid")
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
