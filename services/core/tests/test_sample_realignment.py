"""Feature 23a: the default forecast of the sample shows the alert mockup's gap.

Pure: no database. The forecast is `recurring_pattern` over the sample as known on its
reference day, plus its 4 expected payments, as the loaded sample would forecast it.
"""

import dataclasses
import uuid
from datetime import date

import pytest

from app.fixtures import harbor_street
from app.fixtures.harbor_street import REFERENCE_DAY
from app.modules.forecasting import backtest, strategies

WEEK_OF_NOV_9 = date(2026, 11, 9)
REPEATS = {"once": None, "every_3_months": "quarterly"}


def forecast(seed: int) -> strategies.ForecastResult:
    sample = harbor_street.generate(seed)
    inputs = backtest.inputs_at(sample, REFERENCE_DAY)
    occurrences = tuple(
        strategies.InputOccurrence(
            expected_payment_id=uuid.uuid5(backtest.NAMESPACE, p.description),
            account_id=uuid.uuid5(backtest.NAMESPACE, p.account_key),
            amount_cents=p.amount_cents,
            currency=p.currency,
            description=p.description,
            date=p.date,
            repeats=REPEATS[p.repeats],  # type: ignore[arg-type]
        )
        for p in sample.expected_payments
    )
    inputs = dataclasses.replace(inputs, open_occurrences=occurrences)
    return strategies.STRATEGIES["recurring_pattern"].forecast(inputs)


def ends(result: strategies.ForecastResult) -> dict[date, int]:
    return {w.starts_on: w.end_balance_cents for w in result.weeks}


def test_gap_week_seed_0() -> None:
    """C1."""
    assert ends(forecast(0))[WEEK_OF_NOV_9] == 315000


def test_other_weeks_seed_0() -> None:
    """C2."""
    others = {d: e for d, e in ends(forecast(0)).items() if d != WEEK_OF_NOV_9}
    assert len(others) == 12
    assert all(end >= 1765000 for end in others.values()), others


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_gap_week_other_seeds(seed: int) -> None:
    """C3."""
    assert ends(forecast(seed))[WEEK_OF_NOV_9] < 500000


def test_gap_week_items() -> None:
    """C4."""
    items = [i for i in forecast(0).items if i.source != "estimate"]
    out = {
        (i.date, i.amount_cents, i.description)
        for i in items
        if date(2026, 11, 9) <= i.date <= date(2026, 11, 15) and i.amount_cents < 0
    }
    assert (date(2026, 11, 12), -1450000, "Coastal Supply Co, quarterly order") in out
    assert (date(2026, 11, 13), -1120000, "Payroll") in out
    incoming = [
        i
        for i in items
        if date(2026, 11, 16) <= i.date <= date(2026, 11, 22) and i.amount_cents > 0
    ]
    largest = max(incoming, key=lambda i: i.amount_cents)
    assert (largest.date, largest.amount_cents, largest.description) == (
        date(2026, 11, 17),
        960000,
        "Birch & Co, invoice 1057",
    )
    assert [i.amount_cents for i in incoming].count(960000) == 1
