"""Spec 21: the week convention (door 6) and the inputs' fingerprint (door 1)."""

import dataclasses
import re
import uuid
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise

from app.modules.forecasting import engine
from app.modules.forecasting.strategies import STRATEGIES, CashAccount
from tests.test_forecast_strategies import (
    CASH,
    TODAY,
    inputs,
    occurrence,
    pattern,
    txn,
)

TORONTO = "America/Toronto"


def test_week_starts() -> None:
    """C11."""
    saturday = engine.business_today(datetime(2026, 9, 26, 10, 0, tzinfo=UTC), TORONTO)
    assert saturday == date(2026, 9, 26)
    starts = engine.week_starts(saturday)
    assert len(starts) == 13
    assert (starts[0], starts[12]) == (date(2026, 9, 28), date(2026, 12, 21))
    assert all(b - a == timedelta(days=7) for a, b in pairwise(starts))
    assert all(d.weekday() == 0 for d in starts)

    monday = engine.business_today(datetime(2026, 9, 28, 14, 0, tzinfo=UTC), TORONTO)
    assert engine.week_starts(monday)[0] == date(2026, 9, 28)

    sunday = engine.business_today(datetime(2026, 9, 28, 2, 0, tzinfo=UTC), TORONTO)
    assert sunday == date(2026, 9, 27)
    assert engine.week_starts(sunday)[0] == date(2026, 9, 28)

    result = STRATEGIES["recurring_pattern"].forecast(
        inputs(open_occurrences=(occurrence(date(2026, 9, 26), 5_000),))
    )
    assert [(i.date, i.week) for i in result.items] == [(date(2026, 9, 26), 1)]


def test_fingerprint() -> None:
    """C31."""
    paid = (txn(date(2026, 8, 15), -380_000), txn(date(2026, 9, 15), -380_000))
    rent = pattern(date(2026, 10, 15), -380_000, transactions=paid)
    given = inputs(
        transactions=paid,
        patterns=(rent,),
        open_occurrences=(occurrence(date(2026, 10, 6), 800_000),),
    )
    sha = engine.fingerprint(given, "recurring_pattern")
    assert re.fullmatch(r"[0-9a-f]{64}", sha)

    refreshed = dataclasses.replace(
        given, patterns=(dataclasses.replace(rent, id=uuid.uuid4()),)
    )
    assert engine.fingerprint(refreshed, "recurring_pattern") == sha
    reordered = dataclasses.replace(given, transactions=tuple(reversed(paid)))
    assert engine.fingerprint(reordered, "recurring_pattern") == sha

    changed = [
        engine.fingerprint(given, "rolling_average"),
        engine.fingerprint(
            dataclasses.replace(given, cash_accounts=(CashAccount(CASH, "CAD", 1),)),
            "recurring_pattern",
        ),
        engine.fingerprint(
            dataclasses.replace(
                given,
                today=TODAY + timedelta(days=1),
                week_starts=engine.week_starts(TODAY + timedelta(days=1)),
            ),
            "recurring_pattern",
        ),
        engine.fingerprint(
            dataclasses.replace(
                given, open_occurrences=(occurrence(date(2026, 10, 7), 800_000),)
            ),
            "recurring_pattern",
        ),
    ]
    assert sha not in changed
    assert len(set(changed)) == len(changed)
