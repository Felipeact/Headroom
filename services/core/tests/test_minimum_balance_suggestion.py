"""Spec 23 AC 3, AC 4: the suggested minimum balance (AD-088)."""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.forecasting import engine
from app.modules.forecasting.strategies import InputTransaction
from tests.test_expected_payments_api import cash_business
from tests.test_forecast_recompute import (
    _registered_and_clock,  # noqa: F401 - autouse: handlers subscribed, clocks fixed
)
from tests.test_transaction_sync import (
    SyncFake,
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
    page,
    sync,
    tx,
)

client = TestClient(app)

# Saturday in Toronto (the tests' NOW): the current week started on Monday 2026-09-21.
TODAY = date(2026, 9, 26)
# The 13 complete weeks before it.
MONDAYS = [date(2026, 6, 22) + timedelta(weeks=n) for n in range(13)]
CASH = uuid.uuid4()
SAVINGS = uuid.uuid4()
CARD = uuid.uuid4()


def t(
    day: date,
    cents: int,
    *,
    account: uuid.UUID = CASH,
    label: str = "normal",
) -> InputTransaction:
    return InputTransaction(
        id=uuid.uuid4(),
        account_id=account,
        date=day,
        amount_cents=cents,
        currency="CAD",
        label=label,
        linked_transaction_id=None,
    )


def base() -> list[InputTransaction]:
    """12 weeks with 230000 out (split across two accounts), one with 900000."""
    rows = []
    for n, monday in enumerate(MONDAYS):
        if n == 5:
            rows.append(t(monday + timedelta(days=2), -900_000))
        else:
            rows.append(t(monday, -130_000))
            rows.append(t(monday + timedelta(days=6), -100_000, account=SAVINGS))
    return rows


def suggest(rows: list[InputTransaction]) -> int | None:
    return engine.suggested_minimum(rows, frozenset({CASH, SAVINGS}), TODAY)


def test_median_rounded_up() -> None:
    """C3."""
    assert suggest(base()) == 460_000
    bumped = base() + [t(m + timedelta(days=3), -4_567) for m in MONDAYS]
    assert suggest(bumped) == 470_000


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param(t(MONDAYS[0], 5_000_000), id="inflow"),
        pytest.param(
            t(MONDAYS[1], -5_000_000, label="internal_transfer"), id="internal"
        ),
        pytest.param(t(MONDAYS[2], -5_000_000, label="in_transit"), id="in_transit"),
        pytest.param(t(MONDAYS[3], -5_000_000, account=CARD), id="excluded_account"),
        pytest.param(t(date(2026, 9, 21), -5_000_000), id="current_week_monday"),
        pytest.param(t(TODAY, -5_000_000), id="today"),
        pytest.param(t(date(2026, 6, 21), -5_000_000), id="before_13_weeks"),
    ],
)
def test_what_counts(extra: InputTransaction) -> None:
    """C4: each of these, added to the base, leaves the suggestion at 460000."""
    assert suggest([*base(), extra, extra]) == 460_000


def test_short_history() -> None:
    """C5: only weeks from the oldest outflow's week count."""
    rows = [t(date(2026, 9, 7), -100_000), t(date(2026, 9, 18), -300_000)]
    assert suggest(rows) == 400_000


def test_no_complete_week() -> None:
    """C6."""
    assert suggest([]) is None
    assert suggest([t(date(2026, 9, 22), -50_000), t(MONDAYS[4], 80_000)]) is None


@pytest.mark.usefixtures("migrated_database")
def test_median_rounded_up_through_the_api() -> None:
    """C3, AC 1: GET answers the suggestion from the synced transactions."""
    cash = cash_business()
    rows = [
        tx(f"out-{n}", cash.plaid_operating, 9_000.0 if n == 5 else 2_300.0, day=m)
        for n, m in enumerate(MONDAYS)
    ]
    fake = SyncFake()
    fake.script = [page([cash.plaid_operating], added=rows)]
    sync(fake, cash.connection)
    response = client.get(
        f"/v1/businesses/{cash.business_id}/minimum-balance",
        headers=cash.caller.headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["suggested_cents"] == 460_000
