"""Spec 24: cash gaps and their explanations, pure (C1-C5)."""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from app.modules.alerts import gaps

MONDAYS = [date(2026, 9, 28) + timedelta(weeks=n) for n in range(13)]
MINIMUM = 500000


@dataclass(frozen=True)
class Week:
    starts_on: date
    end_balance_cents: int


@dataclass(frozen=True)
class Item:
    date: date
    amount_cents: int
    source: str = "recurring_pattern"
    currency: str = "CAD"
    source_id: uuid.UUID | None = None
    description: str | None = None
    counterparty: str | None = None
    schedule: str | None = None


def weeks(below: set[int], *, value: int = 499999) -> list[Week]:
    return [Week(m, value if n in below else 1000000) for n, m in enumerate(MONDAYS, 1)]


@pytest.mark.parametrize(
    ("below", "runs"),
    [
        (set(), []),
        ({7}, [(7, 7)]),
        ({3, 4, 5}, [(3, 5)]),
        ({2, 5}, [(2, 2), (5, 5)]),
        (set(range(1, 14)), [(1, 13)]),
    ],
)
def test_finds_gaps(below: set[int], runs: list[tuple[int, int]]) -> None:
    """C1."""
    found = gaps.find_gaps(weeks(below), MINIMUM)
    assert [(g.starts_on, g.ends_on) for g in found] == [
        (MONDAYS[a - 1], MONDAYS[b - 1] + timedelta(days=6)) for a, b in runs
    ]


def test_finds_gaps_at_the_minimum() -> None:
    """C1: a week ending exactly at the minimum is not below it."""
    assert gaps.find_gaps(weeks({7}, value=MINIMUM), MINIMUM) == []


def test_gap_fields() -> None:
    """C2."""
    two = [
        Week(date(2026, 10, 26), 900000),
        Week(date(2026, 11, 2), 300000),
        Week(date(2026, 11, 9), 200000),
        Week(date(2026, 11, 16), 900000),
    ]
    (gap,) = gaps.find_gaps(two, MINIMUM)
    assert gap == gaps.Gap(
        starts_on=date(2026, 11, 2),
        ends_on=date(2026, 11, 15),
        lowest_balance_cents=200000,
        lowest_week_starts_on=date(2026, 11, 9),
        shortfall_cents=300000,
    )
    tied = [Week(date(2026, 11, 2), 200000), Week(date(2026, 11, 9), 200000)]
    (gap,) = gaps.find_gaps(tied, MINIMUM)
    assert gap.lowest_week_starts_on == date(2026, 11, 2)


GAP = gaps.Gap(
    starts_on=date(2026, 11, 9),
    ends_on=date(2026, 11, 15),
    lowest_balance_cents=315000,
    lowest_week_starts_on=date(2026, 11, 9),
    shortfall_cents=185000,
)


def causes(items: list[Item]) -> list[tuple[date, int]]:
    return [
        (e.date, e.amount_cents) for e in gaps.explain(GAP, items) if e.kind == "cause"
    ]


def test_causes() -> None:
    """C3: window money out is 1000000, so 200000 is the 20% line."""
    items = [
        Item(date(2026, 11, 12), -200000),
        Item(date(2026, 11, 13), -100001),
        Item(date(2026, 11, 13), -99999),
        Item(date(2026, 11, 9), -100000, source="estimate"),
        Item(date(2026, 11, 2), -500000, source="estimate"),
        Item(date(2026, 11, 1), -900000),
        Item(date(2026, 11, 10), 700000),
    ]
    assert causes(items) == [(date(2026, 11, 12), -200000)]
    items[0] = Item(date(2026, 11, 12), -199999)
    assert causes(items) == []
    on_first_day = [
        Item(date(2026, 11, 2), -300000),
        Item(date(2026, 11, 2), -400000),
        Item(date(2026, 11, 14), -300000),
    ]
    assert causes(on_first_day) == [
        (date(2026, 11, 2), -400000),
        (date(2026, 11, 2), -300000),
        (date(2026, 11, 14), -300000),
    ]


def after(items: list[Item]) -> list[tuple[date, int]]:
    return [
        (e.date, e.amount_cents)
        for e in gaps.explain(GAP, items)
        if e.kind == "arrives_after"
    ]


def test_arrives_after() -> None:
    """C4."""
    assert after([Item(date(2026, 11, 22), 100), Item(date(2026, 11, 23), 900)]) == [
        (date(2026, 11, 22), 100)
    ]
    assert after(
        [
            Item(date(2026, 11, 17), 960000),
            Item(date(2026, 11, 16), 500000),
            Item(date(2026, 11, 18), 2000000, source="estimate"),
            Item(date(2026, 11, 15), 3000000),
        ]
    ) == [(date(2026, 11, 17), 960000)]
    assert after([Item(date(2026, 11, 19), 5), Item(date(2026, 11, 18), 5)]) == [
        (date(2026, 11, 18), 5)
    ]
    assert after([Item(date(2026, 11, 23), 5), Item(date(2026, 11, 17), -5)]) == []


def test_item_fields() -> None:
    """C5."""
    source_id = uuid.uuid4()
    out = Item(
        date(2026, 11, 13),
        -1120000,
        source="recurring_pattern",
        source_id=source_id,
        description="Payroll",
        counterparty="Payroll",
        schedule="biweekly",
    )
    arriving = Item(
        date(2026, 11, 17),
        960000,
        source="expected_payment",
        description="Birch & Co, invoice 1057",
    )
    found = gaps.explain(GAP, [out, arriving])
    assert found == [
        gaps.Explanation(
            kind="cause",
            date=date(2026, 11, 13),
            amount_cents=-1120000,
            currency="CAD",
            description="Payroll",
            counterparty="Payroll",
            source="recurring_pattern",
            source_id=source_id,
            schedule="biweekly",
        ),
        gaps.Explanation(
            kind="arrives_after",
            date=date(2026, 11, 17),
            amount_cents=960000,
            currency="CAD",
            description="Birch & Co, invoice 1057",
            counterparty=None,
            source="expected_payment",
            source_id=None,
            schedule=None,
        ),
    ]
