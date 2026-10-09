"""Spec 24 Done when 1: the sample's gap in the week of Nov 9 is one alert (C7)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_forecast_recompute import (
    _registered_and_clock,  # noqa: F401 - autouse: handlers subscribed, clocks fixed
)
from tests.test_recurring_sample import load_sample

pytestmark = pytest.mark.usefixtures("migrated_database")

client = TestClient(app)


def test_sample_gap_alert() -> None:
    """C7: seed 0 as known on 2026-09-26, with the alert mockup's $5,000 minimum."""
    sample = load_sample(0)
    assert sample.get("alerts")["items"] == []
    response = client.put(
        f"/v1/businesses/{sample.business_id}/minimum-balance",
        json={"amount_cents": 500000},
        headers=sample.headers,
    )
    assert response.status_code == 200, response.text

    (alert,) = sample.get("alerts")["items"]
    assert alert["state"] == "open"
    assert (alert["starts_on"], alert["ends_on"]) == ("2026-11-09", "2026-11-15")
    assert alert["lowest_balance_cents"] == 315000
    assert alert["minimum_cents"] == 500000
    assert alert["shortfall_cents"] == 185000
    assert [
        (i["kind"], i["date"], i["amount_cents"], i["description"])
        for i in alert["items"]
    ] == [
        ("cause", "2026-11-12", -1450000, "Coastal Supply Co, quarterly order"),
        ("cause", "2026-11-13", -1120000, "Payroll"),
        ("arrives_after", "2026-11-17", 960000, "Birch & Co, invoice 1057"),
    ]
