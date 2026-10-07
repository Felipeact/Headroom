"""Spec 21: the forecast of the Harbor Street Plumbing sample, seed 0 (AC 13, AC 26)."""

from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest

from app.fixtures import harbor_street
from app.main import app
from app.modules.forecasting import service
from app.modules.forecasting.api import get_now
from tests.test_forecast_recompute import NOW
from tests.test_recurring_sample import Sample, load_sample

pytestmark = pytest.mark.usefixtures("migrated_database")


@pytest.fixture(scope="module")
def sample(migrated_database: None) -> Iterator[Sample]:
    """Loaded with every handler's clock at 6:00 in Toronto on 2026-09-26."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(service, "clock", lambda: NOW)
        loaded = load_sample(0)
    app.dependency_overrides[get_now] = lambda: NOW
    yield loaded
    app.dependency_overrides.pop(get_now, None)


def named(items: list[dict[str, Any]]) -> list[tuple[str, int, str]]:
    return sorted(
        (i["date"], i["amount_cents"], i["description"])
        for i in items
        if i["source"] != "estimate"
    )


def test_named_items(sample: Sample) -> None:
    """C23."""
    forecast = sample.get("forecast")
    assert forecast["as_of"] == "2026-09-26"
    items = [i for i in forecast["items"] if i["source"] != "estimate"]
    card = [i for i in items if i["source"] == "card_payment"]
    others = [i for i in items if i["source"] != "card_payment"]

    payroll = ["10-02", "10-16", "10-30", "11-13", "11-27", "12-11"]
    rent = ["10-15", "11-16", "12-15"]
    software = ["10-07", "11-09", "12-07"]
    assert named(others) == sorted(
        [(f"2026-{d}", -1_120_000, "Payroll") for d in payroll]
        + [(f"2026-{d}", -380_000, "Rent") for d in rent]
        + [(f"2026-{d}", -64_000, "Software subscriptions") for d in software]
        + [
            ("2026-10-06", 800_000, "Acme Co, invoice 1042"),
            ("2026-11-12", -1_450_000, "Coastal Supply Co, quarterly order"),
            ("2026-11-17", 960_000, "Birch & Co, invoice 1057"),
            ("2026-12-07", -300_000, "Equipment lease deposit"),
        ]
    )
    assert [(i["date"], i["description"]) for i in card] == [
        ("2026-10-08", "Business Visa"),
        ("2026-11-09", "Business Visa"),
        ("2026-12-08", "Business Visa"),
    ]
    assert card[0]["amount_cents"] == -245_000
    assert card[1]["amount_cents"] == card[2]["amount_cents"] < 0
    operating = sample.account_id("Operating checking")
    assert {i["account_id"] for i in items} == {operating}

    skipped = {
        (date(2026, 12, 24), -1_120_000),
        (date(2026, 11, 9), -231_000),
        (date(2026, 12, 8), -228_000),
    }
    found = {(i["date"], i["amount_cents"]) for i in items}
    reference = harbor_street.generate(0).future.items
    checked = 0
    for item in reference:
        if (
            item.description == "Client payments"
            or (item.date, item.amount_cents) in skipped
        ):
            continue
        assert (item.date.isoformat(), item.amount_cents) in found, item
        checked += 1
    assert checked == 17


def test_upcoming_next_14_days(sample: Sample) -> None:
    """C40."""
    items = sample.get("upcoming?days=14")["items"]
    assert [(i["description"], i["amount_cents"], i["date"]) for i in items] == [
        ("Payroll", -1_120_000, "2026-10-02"),
        ("Acme Co, invoice 1042", 800_000, "2026-10-06"),
        ("Software subscriptions", -64_000, "2026-10-07"),
        ("Business Visa", -245_000, "2026-10-08"),
    ]
