"""Spec 31: what a bookkeeper may and may not do (C17-C21)."""

import uuid
from typing import Any

import pytest

from app.main import app
from tests.bookkeeper_support import client, sql
from tests.email_support import Mail
from tests.test_alert_check import install_fake
from tests.test_alerts_api import (
    _alerts_clock,  # noqa: F401 - autouse fixture: the alerts clock
    owned,
)
from tests.test_businesses import Caller
from tests.test_expected_payments_api import valid_body
from tests.test_forecast_api import (
    forecast_business,
    request_clock,  # noqa: F401 - fixture: the forecast clock
)
from tests.test_forecast_recompute import (
    _registered_and_clock,  # noqa: F401 - autouse: handlers subscribed, clocks fixed
)
from tests.test_transaction_sync import (
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
)

pytestmark = pytest.mark.usefixtures("migrated_database")

BASE = "/v1/businesses/{business_id}"
# Every route under a business, as (method, path after the business), classified.
OWNER_ONLY = {
    ("PATCH", "/"),
    ("POST", "/invitations"),
    ("DELETE", "/members/{user_id}"),
    ("POST", "/bank/link-token"),
    ("POST", "/bank/connections"),
    ("GET", "/bank/providers"),
    ("POST", "/bank/yodlee/fastlink"),
    ("GET", "/bank/connections"),
    ("GET", "/bank/transactions"),
    ("PATCH", "/bank/accounts/{account_id}"),
    ("POST", "/bank/connections/{connection_id}/link-token"),
    ("POST", "/bank/connections/{connection_id}/repair"),
    ("DELETE", "/bank/connections/{connection_id}"),
    ("PUT", "/minimum-balance"),
    ("POST", "/alerts/{alert_id}/dismiss"),
}
SHARED = {
    ("GET", "/"),
    ("GET", "/members"),
    ("GET", "/recurring-patterns"),
    ("GET", "/expected-payments"),
    ("POST", "/expected-payments"),
    ("PUT", "/expected-payments/{payment_id}"),
    ("DELETE", "/expected-payments/{payment_id}"),
    ("GET", "/forecast"),
    ("GET", "/upcoming"),
    ("GET", "/minimum-balance"),
    ("GET", "/forecast/status"),
    ("GET", "/alerts"),
    ("GET", "/alerts/{alert_id}"),
    ("GET", "/dashboard"),
}
# Only a bookkeeper may call these; an owner gets 403.
BOOKKEEPER_ONLY = {("PUT", "/me/alert-emails")}


def add_bookkeeper(business_id: str | uuid.UUID) -> Caller:
    caller = Caller()
    sql(
        "INSERT INTO memberships (business_id, user_id, role)"
        " VALUES (:b, :u, 'bookkeeper')",
        b=uuid.UUID(str(business_id)),
        u=caller.id,
    )
    return caller


def call(caller: Caller, method: str, path: str, **kwargs: Any) -> Any:
    return client.request(method, path, headers=caller.headers, **kwargs)


def test_every_business_route_is_classified() -> None:
    """C20."""
    found = {
        (method.upper(), path.removeprefix(BASE) or "/")
        for path, operations in app.openapi()["paths"].items()
        if path.startswith(BASE)
        for method in operations
    }
    assert OWNER_ONLY.isdisjoint(SHARED)
    assert found == OWNER_ONLY | SHARED | BOOKKEEPER_ONLY


def test_bookkeeper_can_read(
    monkeypatch: pytest.MonkeyPatch,
    request_clock: Any,  # noqa: F811
) -> None:
    """C17."""
    cash = forecast_business()
    bookkeeper = add_bookkeeper(cash.business_id)
    base = f"/v1/businesses/{cash.business_id}"
    for route in (
        "",
        "/dashboard",
        "/forecast",
        "/forecast/status",
        "/upcoming",
        "/alerts",
        "/expected-payments",
        "/recurring-patterns",
        "/minimum-balance",
        "/members",
    ):
        response = call(bookkeeper, "GET", base + route)
        assert response.status_code == 200, (route, response.text)

    # The routes above read the real forecast; the alert below reads a planted one.
    fake = install_fake(monkeypatch)
    alert_owner, alert_business = owned(fake, {7: 185000})
    alert_reader = add_bookkeeper(alert_business)
    (alert,) = call(
        alert_reader, "GET", f"/v1/businesses/{alert_business}/alerts"
    ).json()["items"]
    one = call(
        alert_reader, "GET", f"/v1/businesses/{alert_business}/alerts/{alert['id']}"
    )
    assert one.status_code == 200
    assert alert_owner.id != alert_reader.id


def test_bookkeeper_manages_expected_payments(
    request_clock: Any,  # noqa: F811
) -> None:
    """C18."""
    cash = forecast_business()
    bookkeeper = add_bookkeeper(cash.business_id)
    base = f"/v1/businesses/{cash.business_id}/expected-payments"

    created = call(bookkeeper, "POST", base, json=valid_body())
    assert created.status_code == 201
    payment_id = created.json()["id"]
    changed = call(
        bookkeeper, "PUT", f"{base}/{payment_id}", json=valid_body(amount_cents=900_000)
    )
    assert changed.status_code == 200
    assert call(bookkeeper, "DELETE", f"{base}/{payment_id}").status_code == 204

    rows = sql(
        "SELECT action, actor_user_id FROM audit_log"
        " WHERE business_id = :b AND action LIKE 'expected_payment.%' ORDER BY id",
        b=uuid.UUID(cash.business_id),
    )
    assert [r[0] for r in rows] == [
        "expected_payment.created",
        "expected_payment.updated",
        "expected_payment.deleted",
    ]
    assert {r[1] for r in rows} == {str(bookkeeper.id)}


def test_bookkeeper_gets_403_from_owner_routes(mail: Mail) -> None:
    """C19."""
    cash_owner, business_id = Caller(), None
    cash_owner.post({"name": "Acme", "province": "ON", "time_zone": "America/Toronto"})
    business_id = cash_owner.get("/v1/businesses").json()["items"][0]["id"]
    bookkeeper = add_bookkeeper(business_id)
    ids = {
        "user_id": uuid.uuid4(),
        "account_id": uuid.uuid4(),
        "connection_id": uuid.uuid4(),
        "alert_id": uuid.uuid4(),
    }
    before = sql(
        "SELECT count(*) FROM audit_log WHERE business_id = :b",
        b=uuid.UUID(business_id),
    )
    for method, route in sorted(OWNER_ONLY):
        path = BASE.format(business_id=business_id) + (
            "" if route == "/" else route.format(**ids)
        )
        response = call(bookkeeper, method, path, json={})
        assert response.status_code == 403, (method, route, response.status_code)
        assert response.json()["detail"] == "You don't have permission to do this."
    after = sql(
        "SELECT count(*) FROM audit_log WHERE business_id = :b",
        b=uuid.UUID(business_id),
    )
    assert before == after
    assert mail.sender.sent == []
    ((name,),) = sql(
        "SELECT name FROM businesses WHERE id = :b", b=uuid.UUID(business_id)
    )
    assert name == "Acme"


def test_strangers_get_404(mail: Mail) -> None:
    """C21."""
    owner_a, business_a = Caller(), None
    owner_a.post({"name": "A Co", "province": "ON", "time_zone": "America/Toronto"})
    business_a = owner_a.get("/v1/businesses").json()["items"][0]["id"]
    owner_b = Caller()
    owner_b.post({"name": "B Co", "province": "ON", "time_zone": "America/Toronto"})
    business_b = owner_b.get("/v1/businesses").json()["items"][0]["id"]
    bookkeeper_a = add_bookkeeper(business_a)
    stranger = Caller()

    calls = [
        ("POST", "/invitations", {"email": "x@example.test"}),
        ("GET", "/members", None),
        ("DELETE", f"/members/{uuid.uuid4()}", None),
        ("PUT", "/me/alert-emails", {"enabled": True}),
    ]
    for caller, business_id in (
        (stranger, business_a),
        (bookkeeper_a, business_b),
    ):
        for method, route, body in calls:
            response = call(
                caller,
                method,
                f"/v1/businesses/{business_id}{route}",
                **({"json": body} if body is not None else {}),
            )
            assert response.status_code == 404, (method, route)
            assert response.json()["detail"] == "Business not found."
