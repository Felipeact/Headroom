"""Spec 20: the expected payment routes (AD-075) and `forecast_inputs.changed` (AD-076)."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import events
from app.audit import AuditLog
from app.db import get_sessionmaker
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.bank_sync.models import BankAccount
from app.modules.bank_sync.plaid import PlaidAccount
from app.modules.forecasting.api import get_now
from app.modules.forecasting.models import ExpectedPayment, ExpectedPaymentMatch
from tests.test_bank_connect import plaid_account
from tests.test_businesses import HARBOR, Caller, _owner
from tests.test_transaction_sync import Connected, make_connection

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

# 12:00 in Toronto on 2026-10-06: "today" for every test here unless it moves the clock.
NOON = datetime(2026, 10, 6, 16, 0, tzinfo=UTC)
ITEM_KEYS = {
    "id",
    "account_id",
    "description",
    "amount_cents",
    "currency",
    "date",
    "repeats",
    "next_date",
    "overdue",
}


def valid_body(**changes: Any) -> dict[str, Any]:
    return {
        "description": "Acme Co, invoice 1042",
        "amount_cents": 800_000,
        "date": "2026-10-20",
        "repeats": None,
        **changes,
    }


@pytest.fixture(autouse=True)
def _clock() -> Iterator[list[datetime]]:
    now = [NOON]
    app.dependency_overrides[get_now] = lambda: now[0]
    yield now
    app.dependency_overrides.pop(get_now, None)


@dataclass(frozen=True)
class Cash:
    """A business with a bank: Operating (primary), Reserve (included), Visa (credit)."""

    caller: Caller
    business_id: str
    connection: Connected
    operating: uuid.UUID
    reserve: uuid.UUID
    visa: uuid.UUID
    plaid_operating: PlaidAccount


def owner_business(name: str = "Expected") -> tuple[Caller, str]:
    return _owner({**HARBOR, "name": f"{name} {uuid.uuid4().hex[:6]}"})


def cash_business() -> Cash:
    caller, business_id = owner_business()
    operating = plaid_account("Operating checking", mask="2381")
    reserve = plaid_account("Reserve savings", subtype="savings", mask="9025")
    visa = plaid_account("Visa", type="credit", subtype="credit card", mask="5530")
    connection = make_connection(business_id, [operating, reserve, visa])
    with get_sessionmaker()() as session:
        rows = {
            a.plaid_account_id: a
            for a in session.scalars(
                select(BankAccount).where(
                    BankAccount.business_id == uuid.UUID(business_id)
                )
            )
        }
        rows[operating.account_id].included = True
        rows[operating.account_id].is_primary = True
        rows[reserve.account_id].included = True
        rows[visa.account_id].included = False
        session.commit()
        ids = {k: v.id for k, v in rows.items()}
    return Cash(
        caller,
        business_id,
        connection,
        ids[operating.account_id],
        ids[reserve.account_id],
        ids[visa.account_id],
        operating,
    )


def path(
    business_id: str | uuid.UUID, payment_id: str | uuid.UUID | None = None
) -> str:
    base = f"/v1/businesses/{business_id}/expected-payments"
    return base if payment_id is None else f"{base}/{payment_id}"


def create(cash: Cash, **changes: Any) -> Any:
    return client.post(
        path(cash.business_id), json=valid_body(**changes), headers=cash.caller.headers
    )


def listed(cash: Cash) -> list[dict[str, Any]]:
    response = client.get(path(cash.business_id), headers=cash.caller.headers)
    assert response.status_code == 200
    items: list[dict[str, Any]] = response.json()["items"]
    return items


def stored(business_id: str) -> list[ExpectedPayment]:
    with get_sessionmaker()() as session:
        return list(
            session.scalars(
                select(ExpectedPayment).where(
                    ExpectedPayment.business_id == uuid.UUID(business_id)
                )
            )
        )


def plant(
    business_id: str,
    description: str,
    day: date,
    *,
    repeats: str | None = None,
    amount_cents: int = 100_000,
    matched_on: tuple[date, ...] = (),
) -> uuid.UUID:
    """A payment written straight to the table, with matches on `matched_on`."""
    payment = ExpectedPayment(
        business_id=uuid.UUID(business_id),
        account_id=uuid.uuid4(),
        description=description,
        amount_cents=amount_cents,
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


def audit_rows(business_id: str) -> list[AuditLog]:
    with get_sessionmaker()() as session:
        return list(
            session.scalars(
                select(AuditLog)
                .where(
                    AuditLog.business_id == uuid.UUID(business_id),
                    AuditLog.target_type == "expected_payment",
                )
                .order_by(AuditLog.id)
            )
        )


def is_problem(response: Any, status: int) -> None:
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"


# S1


def test_create_returns_payment() -> None:
    """C1."""
    cash = cash_business()
    response = create(cash, account_id=str(cash.reserve))

    assert response.status_code == 201
    body = response.json()
    assert set(body) == ITEM_KEYS
    assert body["account_id"] == str(cash.reserve)
    assert body["amount_cents"] == 800_000
    assert body["currency"] == "CAD"
    assert body["next_date"] == "2026-10-20"
    assert body["overdue"] is False
    assert body["repeats"] is None
    rows = stored(cash.business_id)
    assert len(rows) == 1
    row = rows[0]
    assert str(row.id) == body["id"]
    assert (row.account_id, row.amount_cents, row.currency, row.date) == (
        cash.reserve,
        800_000,
        "CAD",
        date(2026, 10, 20),
    )
    assert row.description == "Acme Co, invoice 1042"


def test_defaults_to_primary() -> None:
    """C2."""
    cash = cash_business()
    response = create(cash)
    assert response.status_code == 201
    assert response.json()["account_id"] == str(cash.operating)


def test_account_not_cash() -> None:
    """C3."""
    cash = cash_business()
    other = cash_business()
    choices = [cash.visa, cash.reserve, other.operating, uuid.uuid4()]
    excluded = client.patch(
        f"/v1/businesses/{cash.business_id}/bank/accounts/{cash.reserve}",
        json={"included": False},
        headers=cash.caller.headers,
    )
    assert excluded.status_code == 200
    for account_id in choices:
        response = create(cash, account_id=str(account_id))
        is_problem(response, 409)
        assert response.json()["detail"] == "Choose an account you count as cash."
    assert stored(cash.business_id) == []


def test_no_primary_account() -> None:
    """C4."""
    caller, business_id = owner_business("No bank")
    response = client.post(path(business_id), json=valid_body(), headers=caller.headers)
    is_problem(response, 409)
    assert (
        response.json()["detail"] == "Connect a bank before adding expected payments."
    )
    assert stored(business_id) == []


ACCEPTED: list[dict[str, Any]] = [
    {"description": "  A  "},
    {"description": "x" * 100},
    {"description": "  " + "y" * 100 + "  "},
    {"amount_cents": 1},
    {"amount_cents": -1},
    {"amount_cents": 9_999_999_999},
    {"amount_cents": -9_999_999_999},
    {"date": "2026-07-08"},
    {"date": "2028-10-05"},
    {"repeats": None},
    {"repeats": "weekly"},
    {"repeats": "biweekly"},
    {"repeats": "monthly"},
    {"repeats": "quarterly"},
]
REJECTED: list[dict[str, Any]] = [
    {"description": "   "},
    {"description": "x" * 101},
    {"amount_cents": 0},
    {"amount_cents": 10_000_000_000},
    {"amount_cents": -10_000_000_000},
    {"amount_cents": 1.5},
    {"date": "2026-07-07"},
    {"date": "2028-10-06"},
    {"repeats": "semimonthly"},
    {"repeats": "yearly"},
    {"direction": "in"},
]


def test_body_bounds() -> None:
    """C5."""
    cash = cash_business()
    for changes in REJECTED:
        response = create(cash, **changes)
        is_problem(response, 422)
    assert stored(cash.business_id) == []

    for changes in ACCEPTED:
        response = create(cash, **changes)
        assert response.status_code == 201, (changes, response.text)
        if "description" in changes:
            assert response.json()["description"] == changes["description"].strip()
    descriptions = {r.description for r in stored(cash.business_id)}
    assert "A" in descriptions
    assert "y" * 100 in descriptions
    assert len(stored(cash.business_id)) == len(ACCEPTED)


def test_update_payment() -> None:
    """C6."""
    cash = cash_business()
    created = create(cash).json()
    before = stored(cash.business_id)[0]
    revised = {
        "account_id": str(cash.reserve),
        "description": "Acme Co, invoice 1042 (revised)",
        "amount_cents": -250_000,
        "date": "2026-11-02",
        "repeats": "monthly",
    }

    response = client.put(
        path(cash.business_id, created["id"]), json=revised, headers=cash.caller.headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert {k: body[k] for k in revised} == revised
    after = stored(cash.business_id)[0]
    assert after.created_at == before.created_at

    for bad, status in (
        ({"amount_cents": 0}, 422),
        ({"account_id": str(cash.visa)}, 409),
    ):
        response = client.put(
            path(cash.business_id, created["id"]),
            json={**revised, **bad},
            headers=cash.caller.headers,
        )
        is_problem(response, status)
    unchanged = stored(cash.business_id)[0]
    assert (unchanged.amount_cents, unchanged.account_id) == (-250_000, cash.reserve)


def test_delete_payment() -> None:
    """C7."""
    cash = cash_business()
    payment_id = plant(
        cash.business_id, "Matched", date(2026, 10, 1), matched_on=(date(2026, 10, 1),)
    )

    response = client.delete(
        path(cash.business_id, payment_id), headers=cash.caller.headers
    )

    assert response.status_code == 204
    assert response.content == b""
    assert stored(cash.business_id) == []
    with get_sessionmaker()() as session:
        assert (
            session.scalars(
                select(ExpectedPaymentMatch).where(
                    ExpectedPaymentMatch.expected_payment_id == payment_id
                )
            ).all()
            == []
        )


def test_payment_not_found() -> None:
    """C8."""
    cash = cash_business()
    other = cash_business()
    theirs = plant(other.business_id, "Theirs", date(2026, 10, 20))
    for payment_id in (uuid.uuid4(), theirs):
        put = client.put(
            path(cash.business_id, payment_id),
            json=valid_body(),
            headers=cash.caller.headers,
        )
        is_problem(put, 404)
        assert put.json()["detail"] == "Expected payment not found."
        delete = client.delete(
            path(cash.business_id, payment_id), headers=cash.caller.headers
        )
        is_problem(delete, 404)
        assert delete.json()["detail"] == "Expected payment not found."
    row = stored(other.business_id)[0]
    assert (row.description, row.amount_cents) == ("Theirs", 100_000)


def test_list_upcoming_only() -> None:
    """C9."""
    cash = cash_business()
    bid = cash.business_id
    plant(bid, "Bravo", date(2026, 10, 20))
    plant(bid, "Alpha", date(2026, 10, 20))
    plant(bid, "Late", date(2026, 9, 1))
    plant(bid, "Paid", date(2026, 10, 1), matched_on=(date(2026, 10, 1),))
    plant(bid, "Rent", date(2026, 8, 15), repeats="monthly")

    response = client.get(path(bid), headers=cash.caller.headers)

    assert response.status_code == 200
    assert set(response.json()) == {"items"}
    items = response.json()["items"]
    assert [(i["description"], i["next_date"], i["overdue"]) for i in items] == [
        ("Late", "2026-09-01", True),
        ("Rent", "2026-10-15", False),
        ("Alpha", "2026-10-20", False),
        ("Bravo", "2026-10-20", False),
    ]
    for item in items:
        assert set(item) == ITEM_KEYS

    empty = cash_business()
    assert client.get(path(empty.business_id), headers=empty.caller.headers).json() == {
        "items": []
    }


def test_access_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """C10."""
    a = cash_business()
    b = cash_business()
    mine = plant(a.business_id, "Mine", date(2026, 10, 20))
    plant(b.business_id, "Theirs", date(2026, 10, 20))

    def calls(caller: Caller, business_id: str) -> list[Any]:
        return [
            client.get(path(business_id), headers=caller.headers),
            client.post(path(business_id), json=valid_body(), headers=caller.headers),
            client.put(
                path(business_id, mine), json=valid_body(), headers=caller.headers
            ),
            client.delete(path(business_id, mine), headers=caller.headers),
        ]

    for response in calls(Caller(), a.business_id) + calls(a.caller, b.business_id):
        is_problem(response, 404)
        assert response.json()["detail"] == "Business not found."

    assert [i["id"] for i in listed(a)] == [str(mine)]

    monkeypatch.setattr(
        accounts_service,
        "get_membership",
        lambda *_, **__: SimpleNamespace(role="viewer"),
    )
    for response in calls(a.caller, a.business_id):
        is_problem(response, 403)
        assert response.json()["detail"] == "You don't have permission to do this."
    monkeypatch.undo()
    assert {r.description for r in stored(b.business_id)} == {"Theirs"}
    assert {r.description for r in stored(a.business_id)} == {"Mine"}


def test_invalid_ids() -> None:
    """C11."""
    cash = cash_business()
    headers = cash.caller.headers
    is_problem(client.get(path("not-a-uuid"), headers=headers), 422)
    is_problem(
        client.put(
            path(cash.business_id, "not-a-uuid"), json=valid_body(), headers=headers
        ),
        422,
    )
    is_problem(
        client.delete(path(cash.business_id, "not-a-uuid"), headers=headers), 422
    )


def test_audited() -> None:
    """C12."""
    cash = cash_business()
    created = create(cash).json()
    client.put(
        path(cash.business_id, created["id"]),
        json=valid_body(amount_cents=500_000),
        headers=cash.caller.headers,
    )
    client.delete(path(cash.business_id, created["id"]), headers=cash.caller.headers)
    assert create(cash, amount_cents=0).status_code == 422

    rows = audit_rows(cash.business_id)
    assert [r.action for r in rows] == [
        "expected_payment.created",
        "expected_payment.updated",
        "expected_payment.deleted",
    ]
    for row in rows:
        assert row.target_type == "expected_payment"
        assert row.target_id == created["id"]
        details = str(row.details)
        assert "Acme" not in details
        assert "800000" not in details and "500000" not in details


def test_next_date_rules(_clock: list[datetime]) -> None:
    """C25: today is 2026-10-20."""
    _clock[0] = datetime(2026, 10, 20, 16, 0, tzinfo=UTC)
    cash = cash_business()
    bid = cash.business_id
    plant(bid, "Monthly 1st", date(2026, 9, 1), repeats="monthly")
    plant(bid, "Monthly 10th", date(2026, 9, 10), repeats="monthly")
    plant(
        bid,
        "Weekly",
        date(2026, 10, 1),
        repeats="weekly",
        matched_on=(date(2026, 10, 8),),
    )
    plant(bid, "Old one-off", date(2026, 9, 1))
    plant(bid, "Today one-off", date(2026, 10, 20))
    plant(bid, "Matched one-off", date(2026, 10, 6), matched_on=(date(2026, 10, 6),))

    found = {i["description"]: (i["next_date"], i["overdue"]) for i in listed(cash)}

    assert found == {
        "Monthly 1st": ("2026-11-01", False),
        "Monthly 10th": ("2026-10-10", True),
        "Weekly": ("2026-10-15", True),
        "Old one-off": ("2026-09-01", True),
        "Today one-off": ("2026-10-20", False),
    }


# S4


@pytest.fixture
def changes() -> Iterator[list[tuple[events.Event, list[ExpectedPayment]]]]:
    """Each `forecast_inputs.changed`, with the payments a new session sees right then."""
    seen: list[tuple[events.Event, list[ExpectedPayment]]] = []

    def record(event: events.Event) -> None:
        seen.append((event, stored(str(event.business_id))))

    events.subscribe("forecast_inputs.changed", record)
    yield seen
    events.unsubscribe("forecast_inputs.changed", record)


def test_event_after_commit(
    changes: list[tuple[events.Event, list[ExpectedPayment]]],
) -> None:
    """C30."""
    cash = cash_business()
    created = create(cash).json()
    client.put(
        path(cash.business_id, created["id"]),
        json=valid_body(amount_cents=500_000),
        headers=cash.caller.headers,
    )
    client.delete(path(cash.business_id, created["id"]), headers=cash.caller.headers)

    assert len(changes) == 3
    for event, _ in changes:
        assert event.name == "forecast_inputs.changed"
        assert event.business_id == uuid.UUID(cash.business_id)
        assert dict(event.payload) == {
            "source": "expected_payments",
            "expected_payment_id": created["id"],
        }
    assert [r.amount_cents for r in changes[0][1]] == [800_000]
    assert [r.amount_cents for r in changes[1][1]] == [500_000]
    assert changes[2][1] == []


def test_event_not_on_failure(
    changes: list[tuple[events.Event, list[ExpectedPayment]]],
) -> None:
    """C31."""
    cash = cash_business()
    headers = cash.caller.headers
    assert create(cash, account_id=str(cash.visa)).status_code == 409
    assert create(cash, amount_cents=0).status_code == 422
    missing = uuid.uuid4()
    assert (
        client.put(
            path(cash.business_id, missing), json=valid_body(), headers=headers
        ).status_code
        == 404
    )
    assert (
        client.delete(path(cash.business_id, missing), headers=headers).status_code
        == 404
    )
    assert changes == []


def test_dates_follow_the_business_time_zone(_clock: list[datetime]) -> None:
    """AC 5's "today" is business-local: 02:00 UTC on Oct 7 is still Oct 6 in Toronto."""
    _clock[0] = datetime(2026, 10, 7, 2, 0, tzinfo=UTC)
    cash = cash_business()
    assert create(cash, date="2026-07-08").status_code == 201
    assert (
        create(cash, date=str(date(2026, 7, 8) - timedelta(days=1))).status_code == 422
    )
