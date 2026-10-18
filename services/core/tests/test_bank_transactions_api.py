"""Spec 18: `GET /v1/businesses/{business_id}/bank/transactions` (AD-067)."""

import base64
import uuid
from collections.abc import Sequence
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import get_sessionmaker
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync.models import BankAccount, BankConnection, BankTransaction
from app.modules.bank_sync.plaid import PlaidTransaction
from tests.test_businesses import HARBOR, Caller, _owner
from tests.test_transaction_sync import (
    Connected,
    SyncFake,
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
    checking,
    make_connection,
    page,
    sync,
    tx,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

ITEM_KEYS = {
    "id",
    "account_id",
    "date",
    "amount_cents",
    "currency",
    "pending",
    "description",
    "counterparty",
    "label",
}


def path(business_id: str | uuid.UUID) -> str:
    return f"/v1/businesses/{business_id}/bank/transactions"


def get(caller: Caller, business_id: str | uuid.UUID, **params: Any) -> Any:
    return client.get(path(business_id), params=params, headers=caller.headers)


def owner_business() -> tuple[Caller, str]:
    return _owner({**HARBOR, "name": f"Tx {uuid.uuid4().hex[:6]}"})


def with_transactions(
    business_id: str, transactions: Sequence[tuple[str, float, date]]
) -> Connected:
    """A connection of the business, synced once with these (name, Plaid amount, day)."""
    account = checking()
    c = make_connection(business_id, [account])
    fake = SyncFake()
    added: list[PlaidTransaction] = [
        tx(name, account, amount, day=day, name=f"Payment {name}")
        for name, amount, day in transactions
    ]
    fake.script = [page([account], added=added)]
    sync(fake, c)
    return c


def stored_ids(business_id: str) -> set[str]:
    with get_sessionmaker()() as session:
        return {
            str(i)
            for i in session.scalars(
                select(BankTransaction.id).where(
                    BankTransaction.business_id == uuid.UUID(business_id)
                )
            )
        }


def follow(caller: Caller, business_id: str, **params: Any) -> list[list[dict]]:
    pages = []
    cursor = None
    while True:
        query = dict(params, **({"cursor": cursor} if cursor else {}))
        response = get(caller, business_id, **query)
        assert response.status_code == 200
        body = response.json()
        pages.append(body["items"])
        cursor = body["next_cursor"]
        if cursor is None:
            return pages


def test_order_and_shape() -> None:
    """C30."""
    caller, business_id = owner_business()
    with_transactions(
        business_id,
        [
            ("a", 12.5, date(2026, 9, 1)),
            ("b", -200.0, date(2026, 9, 3)),
            ("c", 30.0, date(2026, 9, 3)),
            ("d", 4.0, date(2026, 9, 2)),
            ("e", -15.25, date(2026, 9, 1)),
        ],
    )
    response = get(caller, business_id)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "next_cursor"}
    items = body["items"]
    assert len(items) == 5
    assert all(set(item) == ITEM_KEYS for item in items)
    keys = [(item["date"], item["id"]) for item in items]
    assert keys == sorted(keys, reverse=True)
    by_description = {item["description"]: item for item in items}
    # Plaid's positive amount is money out; ours is negative.
    assert by_description["Payment a"]["amount_cents"] == -1250
    assert by_description["Payment b"]["amount_cents"] == 20000
    assert by_description["Payment e"]["amount_cents"] == 1525
    assert {item["currency"] for item in items} == {"CAD"}


def test_pages_visit_each_once() -> None:
    """C31."""
    caller, business_id = owner_business()
    start = date(2026, 1, 1)
    with_transactions(
        business_id,
        [(f"t{n}", 1.0 + n, start + timedelta(days=n % 40)) for n in range(205)],
    )

    first = get(caller, business_id).json()
    assert len(first["items"]) == 100
    assert first["next_cursor"] is not None

    pages = follow(caller, business_id)
    assert [len(p) for p in pages] == [100, 100, 5]
    ids = [item["id"] for p in pages for item in p]
    assert len(ids) == len(set(ids)) == 205
    assert set(ids) == stored_ids(business_id)
    flat = [(item["date"], item["id"]) for p in pages for item in p]
    assert flat == sorted(flat, reverse=True)

    everything = get(caller, business_id, limit=500).json()
    assert len(everything["items"]) == 205
    assert everything["next_cursor"] is None


def test_empty_business() -> None:
    """C32."""
    caller, business_id = owner_business()
    response = get(caller, business_id)

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": None}


def _b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 501},
        {"limit": "abc"},
        {"cursor": "!!!"},
        {"cursor": _b64("not-a-date/xyz")},
    ],
    ids=[
        "limit-0",
        "limit-501",
        "limit-abc",
        "cursor-not-base64",
        "cursor-bad-content",
    ],
)
def test_invalid_params_422(params: dict[str, Any]) -> None:
    """C33."""
    caller, business_id = owner_business()
    response = get(caller, business_id, **params)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["status"] == 422


def test_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """C34."""
    caller, business_a = owner_business()
    _, business_b = owner_business()
    with_transactions(business_a, [("mine", 5.0, date(2026, 9, 1))])
    with_transactions(business_b, [("theirs", 7.0, date(2026, 9, 1))])

    stranger = Caller()
    not_member = get(stranger, business_a)
    assert not_member.status_code == 404
    assert not_member.json()["detail"] == "Business not found."

    foreign = get(caller, business_b)
    assert foreign.status_code == 404

    mine = get(caller, business_a).json()["items"]
    assert {item["id"] for item in mine} == stored_ids(business_a)
    assert not {item["id"] for item in mine} & stored_ids(business_b)

    monkeypatch.setattr(
        accounts_service,
        "get_membership",
        lambda *_, **__: SimpleNamespace(role="viewer"),
    )
    forbidden = get(caller, business_a)
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "You don't have permission to do this."


def test_no_plaid_ids() -> None:
    """C35."""
    caller, business_id = owner_business()
    c = with_transactions(
        business_id,
        [("x", 5.0, date(2026, 9, 1)), ("y", -9.0, date(2026, 9, 2))],
    )
    with get_sessionmaker()() as session:
        values = [
            *session.scalars(
                select(BankTransaction.provider_transaction_id).where(
                    BankTransaction.business_id == c.business_id
                )
            ),
            *session.scalars(
                select(BankAccount.provider_account_id).where(
                    BankAccount.business_id == c.business_id
                )
            ),
            *session.scalars(
                select(BankConnection.provider_item_id).where(
                    BankConnection.business_id == c.business_id
                )
            ),
        ]
    assert len(values) == 4
    text = get(caller, business_id).text
    for value in values:
        assert value not in text
    for key in ("provider_transaction_id", "provider_account_id", "provider_item_id"):
        assert key not in text
