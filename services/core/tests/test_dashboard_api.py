"""Spec 26: `GET /v1/businesses/{business_id}/dashboard` (AD-102, AD-103)."""

import ast
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app import dashboard, subscriptions
from app.db import get_sessionmaker
from app.main import app
from app.modules.alerts.models import Alert
from app.modules.bank_sync.models import BankAccount
from app.modules.forecasting import service as forecasting_service
from app.modules.forecasting.api import get_now as forecasting_get_now
from app.modules.forecasting.models import ForecastItem, ForecastSnapshot, ForecastWeek
from tests.test_bank_connect import plaid_account
from tests.test_businesses import Caller
from tests.test_expected_payments_api import cash_business, owner_business
from tests.test_recurring_sample import Sample, load_sample
from tests.test_transaction_sync import make_connection
from tests.tokens import bearer

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

# 6:00 in Toronto on Saturday 2026-09-26, the sample's reference day.
NOW = datetime(2026, 9, 26, 10, 0, tzinfo=UTC)
TOP_KEYS = {
    "as_of",
    "currency",
    "cash_on_hand_cents",
    "available_credit_cents",
    "minimum_balance_cents",
    "projected_low",
    "next_card_payment",
    "accounts",
    "connections",
    "forecast",
    "alerts",
    "upcoming",
}
ACCOUNT_KEYS = {
    "id",
    "connection_id",
    "institution_name",
    "name",
    "type",
    "mask",
    "currency",
    "balance_cents",
    "available_cents",
    "included",
    "primary",
    "next_payment_on",
}
WEEK_KEYS = {
    "number",
    "starts_on",
    "ends_on",
    "end_balance_cents",
    "low_cents",
    "high_cents",
}


def _set_clocks(monkeypatch: pytest.MonkeyPatch) -> None:
    subscriptions.register()
    monkeypatch.setattr(forecasting_service, "clock", lambda: NOW)
    app.dependency_overrides[forecasting_get_now] = lambda: NOW
    app.dependency_overrides[dashboard.get_now] = lambda: NOW


def _clear_clocks() -> None:
    app.dependency_overrides.pop(forecasting_get_now, None)
    app.dependency_overrides.pop(dashboard.get_now, None)


@pytest.fixture(autouse=True)
def _clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    _set_clocks(monkeypatch)
    yield
    _clear_clocks()


@pytest.fixture(scope="module")
def sample(migrated_database: None) -> Iterator[Sample]:
    """Seed 0 as known on 2026-09-26, with the mockups' $5,000 minimum."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        _set_clocks(monkeypatch)
        loaded = load_sample(0)
        response = client.put(
            f"/v1/businesses/{loaded.business_id}/minimum-balance",
            json={"amount_cents": 500000},
            headers=loaded.headers,
        )
        assert response.status_code == 200, response.text
        yield loaded
        _clear_clocks()


def get_dashboard(business_id: str, headers: dict[str, str]) -> dict[str, Any]:
    response = client.get(f"/v1/businesses/{business_id}/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def account_by_name(body: dict[str, Any], name: str) -> dict[str, Any]:
    (found,) = [a for a in body["accounts"] if a["name"] == name]
    return found


def test_sample_summary(sample: Sample) -> None:
    """C1."""
    body = get_dashboard(sample.business_id, sample.headers)
    assert set(body) == TOP_KEYS
    assert body["as_of"] == "2026-09-26"
    assert body["currency"] == "CAD"
    assert body["cash_on_hand_cents"] == 4230000
    assert body["available_credit_cents"] == 2000000
    assert body["minimum_balance_cents"] == 500000
    assert body["projected_low"] == {
        "week_starts_on": "2026-11-09",
        "balance_cents": 315000,
    }
    assert body["next_card_payment"] == {
        "account_id": account_by_name(body, "Business Visa")["id"],
        "date": "2026-10-08",
        "amount_cents": -245000,
    }


def test_sample_accounts(sample: Sample) -> None:
    """C2."""
    body = get_dashboard(sample.business_id, sample.headers)
    for account in body["accounts"]:
        assert set(account) == ACCOUNT_KEYS
    operating = account_by_name(body, "Operating checking")
    assert (
        operating["institution_name"],
        operating["mask"],
        operating["balance_cents"],
        operating["included"],
        operating["primary"],
        operating["next_payment_on"],
    ) == ("Harbor Community Bank", "2381", 800000, True, True, None)
    reserve = account_by_name(body, "Reserve savings")
    assert (
        reserve["mask"],
        reserve["balance_cents"],
        reserve["included"],
        reserve["next_payment_on"],
    ) == ("9025", 3430000, True, None)
    line = account_by_name(body, "Line of credit")
    assert (line["mask"], line["available_cents"], line["next_payment_on"]) == (
        "7702",
        2000000,
        None,
    )
    visa = account_by_name(body, "Business Visa")
    assert (visa["institution_name"], visa["mask"], visa["next_payment_on"]) == (
        "Summit Federal",
        "5530",
        "2026-10-08",
    )
    assert len(body["connections"]) == 2
    for connection in body["connections"]:
        assert set(connection) == {"id", "institution_name", "status", "last_synced_at"}
        assert (
            connection["last_synced_at"].replace("+00:00", "Z")
            == "2026-09-26T10:02:00Z"
        )


def test_sample_forecast(sample: Sample) -> None:
    """C3."""
    body = get_dashboard(sample.business_id, sample.headers)
    forecast = body["forecast"]
    assert set(forecast) == {
        "id",
        "computed_at",
        "opening_balance_cents",
        "incomplete",
        "weeks",
    }
    assert forecast["opening_balance_cents"] == 4230000
    assert len(forecast["weeks"]) == 13
    full = sample.get("forecast")
    for week, source in zip(forecast["weeks"], full["weeks"], strict=True):
        assert set(week) == WEEK_KEYS
        assert week == {k: source[k] for k in WEEK_KEYS}
    (gap,) = [w for w in forecast["weeks"] if w["starts_on"] == "2026-11-09"]
    assert gap["end_balance_cents"] == 315000
    assert "items" not in forecast


def test_sample_alerts_upcoming(sample: Sample) -> None:
    """C4."""
    body = get_dashboard(sample.business_id, sample.headers)
    assert body["alerts"] == sample.get("alerts")["items"]
    (alert,) = body["alerts"]
    assert [f["kind"] for f in alert["fixes"]] == [
        "pay_early",
        "move_payment",
        "draw_credit",
    ]
    assert body["upcoming"] == sample.get("upcoming?days=14")["items"]
    assert [
        (i["description"], i["amount_cents"], i["date"]) for i in body["upcoming"]
    ] == [
        ("Payroll", -1_120_000, "2026-10-02"),
        ("Acme Co, invoice 1042", 800_000, "2026-10-06"),
        ("Software subscriptions", -64_000, "2026-10-07"),
        ("Business Visa", -245_000, "2026-10-08"),
    ]


def set_accounts(business_id: str, changes: dict[uuid.UUID, dict[str, Any]]) -> None:
    with get_sessionmaker()() as session:
        for account_id, values in changes.items():
            session.execute(
                update(BankAccount).where(BankAccount.id == account_id).values(**values)
            )
        session.commit()


def add_accounts(business_id: str, *specs: dict[str, Any]) -> list[uuid.UUID]:
    """Stored accounts on a new connection, each then set to the values in `specs`."""
    names = [f"Extra {n} {uuid.uuid4().hex[:4]}" for n in range(len(specs))]
    make_connection(business_id, [plaid_account(name) for name in names])
    with get_sessionmaker()() as session:
        rows = {
            a.name: a.id
            for a in session.scalars(
                select(BankAccount).where(BankAccount.name.in_(names))
            )
        }
    ids = [rows[name] for name in names]
    set_accounts(business_id, dict(zip(ids, specs, strict=True)))
    return ids


def test_cash_on_hand() -> None:
    """C5."""
    cash = cash_business()
    set_accounts(
        cash.business_id,
        {
            cash.operating: {"balance_cents": 100000},
            cash.reserve: {"balance_cents": 50000},
            cash.visa: {"balance_cents": 30000},
        },
    )
    add_accounts(
        cash.business_id,
        {"type": "savings", "included": True, "balance_cents": None},
        {"type": "checking", "included": False, "balance_cents": 70000},
        # Credit can't be included (ck_bank_accounts_included_cash); it never counts.
        {"type": "credit_card", "included": False, "balance_cents": 30000},
        {"type": "line_of_credit", "included": False, "balance_cents": 90000},
    )
    headers = cash.caller.headers
    assert get_dashboard(cash.business_id, headers)["cash_on_hand_cents"] == 150000
    set_accounts(cash.business_id, {cash.reserve: {"included": False}})
    assert get_dashboard(cash.business_id, headers)["cash_on_hand_cents"] == 100000


def test_available_credit() -> None:
    """C6."""
    cash = cash_business()
    assert (
        get_dashboard(cash.business_id, cash.caller.headers)["available_credit_cents"]
        is None
    )
    add_accounts(
        cash.business_id,
        {"type": "line_of_credit", "included": False, "available_cents": 300000},
        {"type": "line_of_credit", "included": False, "available_cents": None},
        {
            "type": "line_of_credit",
            "included": False,
            "available_cents": 500000,
            "currency": "USD",
        },
    )
    body = get_dashboard(cash.business_id, cash.caller.headers)
    assert body["available_credit_cents"] == 300000


def plant_snapshot(
    business_id: str,
    ends: list[int],
    items: list[tuple[date, int, str, uuid.UUID]] = (),  # type: ignore[assignment]
    *,
    paid_from: uuid.UUID,
    card_id: uuid.UUID,
) -> None:
    """A snapshot from Saturday 2026-09-26 whose week n ends at `ends[n - 1]`.

    Card payments go out of `paid_from`, with the card as `source_id` (spec 21 AC 10).
    """
    first_monday = date(2026, 9, 28)
    snapshot = ForecastSnapshot(
        id=uuid.uuid4(),
        business_id=uuid.UUID(business_id),
        inputs_sha256=uuid.uuid4().hex * 2,
        strategy="recurring_pattern",
        as_of=date(2026, 9, 26),
        currency="CAD",
        opening_balance_cents=500000,
        last_computed_at=NOW,
    )
    with get_sessionmaker()() as session:
        session.add(snapshot)
        session.flush()
        session.add_all(
            ForecastWeek(
                snapshot_id=snapshot.id,
                number=n,
                starts_on=first_monday + timedelta(weeks=n - 1),
                end_balance_cents=end,
                low_cents=end - 1000,
                high_cents=end + 1000,
                money_in_cents=0,
                money_out_cents=0,
            )
            for n, end in enumerate(ends, start=1)
        )
        session.add_all(
            ForecastItem(
                id=item_id,
                snapshot_id=snapshot.id,
                week=1,
                date=day,
                account_id=paid_from,
                amount_cents=cents,
                currency="CAD",
                source=source,
                source_id=card_id if source == "card_payment" else None,
                description="Visa",
                counterparty=None,
                schedule=None,
            )
            for day, cents, source, item_id in items
        )
        session.commit()


def test_projected_low_and_card() -> None:
    """C7."""
    cash = cash_business()
    ends = [900000] * 13
    ends[3] = ends[8] = 120000
    low_id, high_id = sorted([uuid.uuid4(), uuid.uuid4()])
    plant_snapshot(
        cash.business_id,
        ends,
        [
            (date(2026, 9, 25), -10000, "card_payment", uuid.uuid4()),
            (date(2026, 9, 30), -30000, "card_payment", high_id),
            (date(2026, 9, 30), -20000, "card_payment", low_id),
            (date(2026, 9, 29), -5000, "recurring_pattern", uuid.uuid4()),
        ],
        paid_from=cash.operating,
        card_id=cash.visa,
    )
    body = get_dashboard(cash.business_id, cash.caller.headers)
    assert body["projected_low"] == {
        "week_starts_on": "2026-10-19",
        "balance_cents": 120000,
    }
    assert body["next_card_payment"] == {
        "account_id": str(cash.visa),
        "date": "2026-09-30",
        "amount_cents": -20000,
    }


def test_no_forecast() -> None:
    """C8."""
    cash = cash_business()
    set_accounts(
        cash.business_id,
        {cash.operating: {"balance_cents": 100000}, cash.reserve: {"balance_cents": 0}},
    )
    body = get_dashboard(cash.business_id, cash.caller.headers)
    assert body["forecast"] is None
    assert body["projected_low"] is None
    assert body["next_card_payment"] is None
    assert body["upcoming"] == []
    assert body["alerts"] == []
    assert body["minimum_balance_cents"] is None
    assert body["cash_on_hand_cents"] == 100000
    assert {a["name"] for a in body["accounts"]} >= {
        "Operating checking",
        "Reserve savings",
    }


def test_open_only(sample: Sample) -> None:
    """C9: on a second sample, so the module's sample keeps its open alert."""
    other = load_sample(0)
    client.put(
        f"/v1/businesses/{other.business_id}/minimum-balance",
        json={"amount_cents": 500000},
        headers=other.headers,
    )
    (alert,) = get_dashboard(other.business_id, other.headers)["alerts"]
    response = client.post(
        f"/v1/businesses/{other.business_id}/alerts/{alert['id']}/dismiss",
        headers=other.headers,
    )
    assert response.status_code == 200, response.text
    assert get_dashboard(other.business_id, other.headers)["alerts"] == []

    with get_sessionmaker()() as session:
        session.execute(
            update(Alert)
            .where(Alert.id == uuid.UUID(alert["id"]))
            .values(state="resolved", resolved_at=NOW)
        )
        session.commit()
    assert get_dashboard(other.business_id, other.headers)["alerts"] == []
    # The module's sample still shows its open alert.
    assert len(get_dashboard(sample.business_id, sample.headers)["alerts"]) == 1


def test_access_denied(sample: Sample) -> None:
    """C10."""
    url = f"/v1/businesses/{sample.business_id}/dashboard"
    stranger = Caller()
    other_owner, _ = owner_business("Other")
    for caller in (stranger, other_owner):
        response = client.get(url, headers=caller.headers)
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["detail"] == "Business not found."
        assert "Operating checking" not in response.text
    assert client.get(url).status_code == 401
    assert client.get(url, headers=bearer("not-a-token")).status_code == 401
    response = client.get("/v1/businesses/not-a-uuid/dashboard", headers=sample.headers)
    assert response.status_code == 422


def test_read_router_imports() -> None:
    """C11: the read router reaches modules only through their service.py (door 1)."""
    source = Path(dashboard.__file__).read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported += [f"{node.module}.{a.name}" for a in node.names]
        elif isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
    from_modules = [name for name in imported if name.startswith("app.modules.")]
    assert from_modules, imported
    for name in from_modules:
        parts = name.split(".")
        assert len(parts) == 4 and parts[3] == "service", name
    paths = app.openapi()["paths"]
    route = paths["/v1/businesses/{business_id}/dashboard"]["get"]
    assert route["tags"] == ["dashboard"]
