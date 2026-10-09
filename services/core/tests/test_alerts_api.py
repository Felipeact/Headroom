"""Spec 24: the alerts routes (C18, C21-C27, C30)."""

import json
import uuid
from collections.abc import Iterator
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import events
from app.main import app
from app.modules.accounts import service as accounts_service
from app.modules.alerts.api import get_now
from tests.test_alert_check import (
    NOW,
    Fake,
    alerts_of,
    check,
    forecast,
    install_fake,
    listening,
    payroll,
)
from tests.test_businesses import Caller
from tests.test_expected_payments_api import is_problem, owner_business
from tests.test_export_openapi import CONTRACT
from tests.test_forecast_recompute import (
    _registered_and_clock,  # noqa: F401 - autouse: handlers subscribed, clocks fixed
)

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)

ALERT_KEYS = {
    "id",
    "state",
    "starts_on",
    "ends_on",
    "lowest_week_starts_on",
    "lowest_balance_cents",
    "minimum_cents",
    "shortfall_cents",
    "currency",
    "created_at",
    "updated_at",
    "dismissed_at",
    "resolved_at",
    "items",
}
ITEM_KEYS = {
    "kind",
    "date",
    "amount_cents",
    "currency",
    "description",
    "counterparty",
    "source",
    "schedule",
}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Fake:
    return install_fake(monkeypatch)


@pytest.fixture
def sent() -> Iterator[list[events.Event]]:
    with listening() as seen:
        yield seen


@pytest.fixture(autouse=True)
def _alerts_clock() -> Any:
    app.dependency_overrides[get_now] = lambda: NOW
    yield
    app.dependency_overrides.pop(get_now, None)


def owned(fake: Fake, shortfalls: dict[int, int]) -> tuple[Caller, uuid.UUID]:
    caller, business_id = owner_business("Alerts API")
    found = uuid.UUID(business_id)
    fake.minimums[found] = (500000, "CAD")
    fake.forecasts[found] = forecast(shortfalls)
    check(found)
    return caller, found


def url(business_id: uuid.UUID, rest: str = "alerts") -> str:
    return f"/v1/businesses/{business_id}/{rest}"


def get(caller: Caller, business_id: uuid.UUID, rest: str = "alerts") -> Any:
    response = client.get(url(business_id, rest), headers=caller.headers)
    assert response.status_code == 200, response.text
    return response.json()


def dismiss(caller: Caller, business_id: uuid.UUID, alert_id: Any) -> Any:
    return client.post(
        url(business_id, f"alerts/{alert_id}/dismiss"), headers=caller.headers
    )


def three_states(fake: Fake) -> tuple[Caller, uuid.UUID, dict[str, str]]:
    """Gaps in weeks 2, 5 and 9: one stays open, one is dismissed, one resolves."""
    caller, business_id = owned(fake, {2: 100000, 5: 200000, 9: 300000})
    by_start = {a.starts_on: str(a.id) for a in alerts_of(business_id)}
    ids = {
        "open": by_start[date(2026, 10, 5)],
        "dismissed": by_start[date(2026, 10, 26)],
        "resolved": by_start[date(2026, 11, 23)],
    }
    assert dismiss(caller, business_id, ids["dismissed"]).status_code == 200
    fake.forecasts[business_id] = forecast({2: 100000, 5: 200000})
    check(business_id)
    return caller, business_id, ids


def test_dismiss_open(fake: Fake, sent: list[events.Event]) -> None:
    """C18."""
    caller, business_id = owned(fake, {7: 185000})
    (alert,) = alerts_of(business_id)
    sent.clear()
    response = dismiss(caller, business_id, alert.id)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "dismissed"
    assert body["dismissed_at"] is not None
    (row,) = alerts_of(business_id)
    assert row.notified_shortfall_cents == row.shortfall_cents == 185000
    assert sent == []


def test_dismiss_resolved_or_dismissed(fake: Fake) -> None:
    """C21."""
    caller, business_id, ids = three_states(fake)
    before = {str(a.id): a.updated_at for a in alerts_of(business_id)}
    response = dismiss(caller, business_id, ids["resolved"])
    is_problem(response, 409)
    assert response.json()["detail"] == "This alert is already resolved."
    dismissed_at = get(caller, business_id, f"alerts/{ids['dismissed']}")[
        "dismissed_at"
    ]
    # A later clock, so rewriting the dismissal would change it.
    app.dependency_overrides[get_now] = lambda: NOW + timedelta(hours=1)
    again = dismiss(caller, business_id, ids["dismissed"])
    assert again.status_code == 200, again.text
    assert again.json()["dismissed_at"] == dismissed_at
    assert {str(a.id): a.updated_at for a in alerts_of(business_id)} == before


def test_list(fake: Fake) -> None:
    """C22."""
    caller, business_id, ids = three_states(fake)
    body = get(caller, business_id)
    assert set(body) == {"items"}
    assert [a["id"] for a in body["items"]] == [ids["open"]]
    for state in ("dismissed", "resolved"):
        found = get(caller, business_id, f"alerts?state={state}")["items"]
        assert [a["id"] for a in found] == [ids[state]]
        assert all(set(a) == ALERT_KEYS for a in found)

    caller, business_id = owned(fake, {})
    fake.forecasts[business_id] = forecast(
        {9: 300000, 3: 100000},
        items=[
            payroll(date(2026, 11, 27)),
            payroll(date(2026, 11, 29)),
            _incoming(date(2026, 12, 1)),
        ],
    )
    check(business_id)
    items = get(caller, business_id)["items"]
    assert [a["starts_on"] for a in items] == ["2026-10-12", "2026-11-23"]
    later = items[1]
    assert set(later) == ALERT_KEYS
    assert [i["kind"] for i in later["items"]] == ["cause", "cause", "arrives_after"]
    assert all(set(i) == ITEM_KEYS for i in later["items"])


def _incoming(day: date) -> Any:
    item = payroll(day)
    return type(item)(**{**item.__dict__, "amount_cents": 960000})


def test_get_one(fake: Fake) -> None:
    """C23."""
    caller, business_id, ids = three_states(fake)
    for state, alert_id in ids.items():
        body = get(caller, business_id, f"alerts/{alert_id}")
        assert (body["id"], body["state"]) == (alert_id, state)
        assert set(body) == ALERT_KEYS


def test_bad_state(fake: Fake) -> None:
    """C24."""
    caller, business_id = owned(fake, {})
    response = client.get(
        url(business_id, "alerts?state=closed"), headers=caller.headers
    )
    is_problem(response, 422)


def test_alert_not_found(fake: Fake) -> None:
    """C25."""
    caller, business_id = owned(fake, {7: 185000})
    _, other = owned(fake, {7: 185000})
    (foreign,) = alerts_of(other)
    for alert_id in (uuid.uuid4(), foreign.id):
        for response in (
            client.get(url(business_id, f"alerts/{alert_id}"), headers=caller.headers),
            dismiss(caller, business_id, alert_id),
        ):
            is_problem(response, 404)
            assert response.json()["detail"] == "Alert not found."
    (still,) = alerts_of(other)
    assert still.state == "open"


def test_access(fake: Fake, monkeypatch: pytest.MonkeyPatch) -> None:
    """C26."""
    caller, business_id = owned(fake, {7: 185000})
    (alert,) = alerts_of(business_id)
    stranger = Caller()
    for response in (
        client.get(url(business_id), headers=stranger.headers),
        client.get(url(business_id, f"alerts/{alert.id}"), headers=stranger.headers),
        dismiss(stranger, business_id, alert.id),
    ):
        is_problem(response, 404)
        assert response.json()["detail"] == "Business not found."

    monkeypatch.setattr(
        accounts_service,
        "get_membership",
        lambda *_, **__: SimpleNamespace(role="viewer"),
    )
    is_problem(dismiss(caller, business_id, alert.id), 403)
    monkeypatch.undo()
    (row,) = alerts_of(business_id)
    assert row.state == "open"


def test_money_and_payloads(fake: Fake, sent: list[events.Event]) -> None:
    """C27."""
    caller, business_id = owned(fake, {7: 185000})
    fake.forecasts[business_id] = forecast(
        {7: 285001}, items=[_incoming(date(2026, 11, 17))]
    )
    check(business_id)
    fake.forecasts[business_id] = forecast({})
    check(business_id)
    assert [e.name for e in sent] == [
        "alert.created",
        "alert.updated",
        "alert.resolved",
    ]
    assert all(set(e.payload) == {"alert_id"} for e in sent)
    (alert,) = get(caller, business_id, "alerts?state=resolved")["items"]
    for key in ("lowest_balance_cents", "minimum_cents", "shortfall_cents"):
        assert type(alert[key]) is int
    assert alert["currency"] == "CAD"
    for item in alert["items"]:
        assert type(item["amount_cents"]) is int
        assert item["currency"] == "CAD"


def test_contract_paths() -> None:
    """C30."""
    paths = json.loads(CONTRACT.read_text(encoding="utf-8"))["paths"]
    base = "/v1/businesses/{business_id}/alerts"
    assert "get" in paths[base]
    assert "get" in paths[base + "/{alert_id}"]
    assert "post" in paths[base + "/{alert_id}/dismiss"]
