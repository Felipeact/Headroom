"""Spec 22: the accuracy history spec 32's report reads (AD-086)."""

import uuid
from datetime import date, timedelta

import pytest

from app.db import get_sessionmaker
from app.main import app
from app.modules.forecasting import service
from app.modules.forecasting.models import ForecastAccuracy
from tests.test_expected_payments_api import cash_business
from tests.test_forecast_accuracy import MONDAY, plant_snapshot

pytestmark = pytest.mark.usefixtures("migrated_database")


def plant_row(
    business_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    week_start: date,
    horizon: int,
    forecast: int,
    actual: int,
) -> None:
    with get_sessionmaker()() as session:
        session.add(
            ForecastAccuracy(
                business_id=business_id,
                week_start=week_start,
                horizon=horizon,
                target_week_start=week_start + timedelta(weeks=horizon - 1),
                snapshot_id=snapshot_id,
                currency="CAD",
                forecast_cents=forecast,
                actual_cents=actual,
                error_cents=forecast - actual,
            )
        )
        session.commit()


def test_accuracy_history() -> None:
    """ACC-19: one horizon from `since` on, by week then business; percent derived."""
    first = uuid.UUID(cash_business().business_id)
    second = uuid.UUID(cash_business().business_id)
    a, b = sorted([first, second], key=str)
    snapshots = {bid: plant_snapshot(bid) for bid in (a, b)}
    # Far-future weeks keep other tests' rows out of the window.
    w1, w2, w3 = (date(2031, 1, 6) + timedelta(weeks=n) for n in range(3))
    plant_row(b, snapshots[b], w2, 4, 110_000, 100_000)
    plant_row(a, snapshots[a], w2, 4, 90_000, 120_000)
    plant_row(a, snapshots[a], w3, 4, 50_000, 0)
    plant_row(a, snapshots[a], w2, 1, 1, 1)
    plant_row(a, snapshots[a], w1, 4, 1, 1)

    with get_sessionmaker()() as session:
        found = service.accuracy_history(session, horizon=4, since=w2)

    assert [(r.week_start, r.business_id) for r in found] == [(w2, a), (w2, b), (w3, a)]
    first_row = found[0]
    assert first_row == service.AccuracyRecord(
        business_id=a,
        week_start=w2,
        horizon=4,
        target_week_start=w2 + timedelta(weeks=3),
        snapshot_id=snapshots[a],
        currency="CAD",
        forecast_cents=90_000,
        actual_cents=120_000,
        error_cents=-30_000,
        error_percent=25.0,
    )
    assert found[1].error_percent == pytest.approx(10.0)
    assert found[2].error_percent is None


@pytest.mark.parametrize("horizon", [0, 2, 5, 14])
def test_accuracy_history_horizons(horizon: int) -> None:
    """ACC-20."""
    with get_sessionmaker()() as session, pytest.raises(ValueError):
        service.accuracy_history(session, horizon=horizon, since=MONDAY)


def test_no_accuracy_route() -> None:
    """ACC-21: the history is read in-process only."""
    paths = app.openapi()["paths"]
    assert paths
    assert not [p for p in paths if "accuracy" in p or "pin" in p]
