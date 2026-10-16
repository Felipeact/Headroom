"""Spec 25: the suggested fix rules, pure (C1-C8)."""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta

import pytest

from app.modules.alerts import gaps

MONDAYS = [date(2026, 9, 28) + timedelta(weeks=n) for n in range(13)]
GAP_MONDAY = date(2026, 11, 9)
GAP = gaps.Gap(
    starts_on=GAP_MONDAY,
    ends_on=date(2026, 11, 15),
    lowest_balance_cents=315000,
    lowest_week_starts_on=GAP_MONDAY,
    shortfall_cents=185000,
)


@dataclass(frozen=True)
class Week:
    starts_on: date
    end_balance_cents: int


def weeks(ends: dict[date, int] | None = None) -> list[Week]:
    """13 weeks at 3000000, the gap week at 315000, except as `ends` says."""
    found = {GAP_MONDAY: 315000} | (ends or {})
    return [Week(m, found.get(m, 3000000)) for m in MONDAYS]


def item(
    kind: gaps.AlertItemKind,
    day: date,
    amount_cents: int,
    description: str,
    counterparty: str | None = None,
) -> gaps.Explanation:
    return gaps.Explanation(
        kind=kind,
        date=day,
        amount_cents=amount_cents,
        currency="CAD",
        description=description,
        counterparty=counterparty,
        source="expected_payment",
        source_id=uuid.uuid4(),
        schedule=None,
    )


COASTAL = item(
    "cause", date(2026, 11, 12), -1450000, "Coastal Supply Co, quarterly order"
)
PAYROLL = item("cause", date(2026, 11, 13), -1120000, "Payroll", "Payroll Co")
BIRCH = item(
    "arrives_after", date(2026, 11, 17), 960000, "Birch & Co, invoice 1057", "Birch"
)
LINE = gaps.CreditLine(name="Line of credit", currency="CAD", available_cents=2000000)


def fixes(
    explained: list[gaps.Explanation],
    lines: list[gaps.CreditLine],
    *,
    gap: gaps.Gap = GAP,
    week_list: list[Week] | None = None,
) -> list[gaps.Fix]:
    return gaps.fixes(gap, explained, week_list or weeks(), lines, currency="CAD")


def of_kind(found: list[gaps.Fix], kind: gaps.FixKind) -> list[gaps.Fix]:
    return [f for f in found if f.kind == kind]


def test_pay_early() -> None:
    """C1: the item arriving after the gap, 7 days earlier (AC 2)."""
    (fix,) = of_kind(fixes([COASTAL, BIRCH], []), "pay_early")
    assert fix.amount_cents == 960000
    assert fix.currency == "CAD"
    assert fix.original_date == date(2026, 11, 17)
    assert fix.date == date(2026, 11, 10)
    assert fix.description == "Birch & Co, invoice 1057"
    assert fix.counterparty == "Birch"
    assert fix.repay_on is None
    assert fix.available_cents is None

    assert of_kind(fixes([COASTAL], []), "pay_early") == []


def test_move_payment() -> None:
    """C2: the largest cause, earliest on a tie, 7 days later (AC 3)."""
    (fix,) = of_kind(fixes([COASTAL, PAYROLL], []), "move_payment")
    assert fix.amount_cents == -1450000
    assert fix.original_date == date(2026, 11, 12)
    assert fix.date == date(2026, 11, 19)
    assert fix.description == "Coastal Supply Co, quarterly order"
    assert fix.counterparty is None
    assert fix.repay_on is None

    later = item("cause", date(2026, 11, 12), -1000000, "Later", "L")
    earlier = item("cause", date(2026, 11, 10), -1000000, "Earlier", "E")
    (fix,) = of_kind(fixes([earlier, later], []), "move_payment")
    assert fix.description == "Earlier"
    assert fix.counterparty == "E"
    assert fix.original_date == date(2026, 11, 10)
    assert fix.date == date(2026, 11, 17)

    assert of_kind(fixes([BIRCH], []), "move_payment") == []


@pytest.mark.parametrize(
    ("lines", "drawn"),
    [
        ([LINE], 200000),
        ([gaps.CreditLine("Line of credit", "CAD", 185000)], 185000),
        ([gaps.CreditLine("Line of credit", "CAD", 184999)], None),
        ([gaps.CreditLine("Line of credit", "USD", 2000000)], None),
        ([gaps.CreditLine("Line of credit", "CAD", None)], None),
        ([], None),
    ],
)
def test_draw_credit(lines: list[gaps.CreditLine], drawn: int | None) -> None:
    """C3: a line qualifies when its available credit covers the shortfall (AC 4, 5)."""
    found = of_kind(fixes([COASTAL, BIRCH], lines), "draw_credit")
    if drawn is None:
        assert found == []
        return
    (fix,) = found
    assert fix.amount_cents == drawn
    assert fix.currency == "CAD"
    assert fix.date == date(2026, 11, 9)
    assert fix.repay_on == date(2026, 11, 17)
    assert fix.original_date is None
    assert fix.description == "Line of credit"
    assert fix.counterparty is None
    assert fix.available_cents == lines[0].available_cents


def test_draw_credit_choice_and_repay() -> None:
    """C3: the line with most credit, by name on a tie; repaid after the gap without
    an arrives-after item."""
    b = gaps.CreditLine("B line", "CAD", 500000)
    a = gaps.CreditLine("A line", "CAD", 2000000)
    (fix,) = of_kind(fixes([COASTAL, BIRCH], [b, a]), "draw_credit")
    assert fix.description == "A line"
    assert fix.available_cents == 2000000

    tied = [gaps.CreditLine("Zed line", "CAD", 500000), b]
    (fix,) = of_kind(fixes([COASTAL], tied), "draw_credit")
    assert fix.description == "B line"
    assert fix.repay_on == date(2026, 11, 16)


def test_financing() -> None:
    """C4: financing for the length of the gap, only without a qualifying line (AC 6, 9)."""
    (fix,) = of_kind(fixes([COASTAL, BIRCH], []), "financing")
    assert fix.amount_cents == 200000
    assert fix.currency == "CAD"
    assert fix.date == date(2026, 11, 9)
    assert fix.repay_on == date(2026, 11, 16)
    assert fix.original_date is None
    assert fix.description is None
    assert fix.counterparty is None
    assert fix.available_cents is None

    found = fixes([COASTAL, BIRCH], [LINE])
    assert of_kind(found, "financing") == []
    assert len(of_kind(found, "draw_credit")) == 1


@pytest.mark.parametrize(
    ("shortfall", "borrowed"),
    [(1, 100000), (185000, 200000), (200000, 200000), (200001, 300000)],
)
def test_borrow_rounding(shortfall: int, borrowed: int) -> None:
    """C5: the shortfall rounded up to a whole $1,000 (AC 4, 6)."""
    gap = gaps.Gap(
        starts_on=GAP_MONDAY,
        ends_on=date(2026, 11, 15),
        lowest_balance_cents=500000 - shortfall,
        lowest_week_starts_on=GAP_MONDAY,
        shortfall_cents=shortfall,
    )
    week_list = weeks({GAP_MONDAY: 500000 - shortfall})
    ample = gaps.CreditLine("Line of credit", "CAD", 10_000_000)
    (draw,) = of_kind(fixes([], [ample], gap=gap, week_list=week_list), "draw_credit")
    assert draw.amount_cents == borrowed
    (financing,) = of_kind(fixes([], [], gap=gap, week_list=week_list), "financing")
    assert financing.amount_cents == borrowed


def test_new_lowest() -> None:
    """C6: the lowest of the 13 weeks after the fix's money moves (AC 7)."""
    week_list = weeks({date(2026, 12, 7): 1795319})
    found = {
        f.kind: f.new_lowest_balance_cents
        for f in fixes([COASTAL, BIRCH], [LINE], week_list=week_list)
    }
    assert found == {
        "move_payment": 1765000,
        "pay_early": 1275000,
        "draw_credit": 515000,
    }

    week_list = weeks({date(2026, 12, 7): 1000000})
    (move,) = of_kind(fixes([COASTAL], [], week_list=week_list), "move_payment")
    assert move.new_lowest_balance_cents == 1000000

    # A gap in the last week, whose cause moves past the forecast's end.
    last = date(2026, 12, 21)
    gap = gaps.Gap(
        starts_on=last,
        ends_on=date(2026, 12, 27),
        lowest_balance_cents=450000,
        lowest_week_starts_on=last,
        shortfall_cents=50000,
    )
    cause = item("cause", date(2026, 12, 23), -100000, "Late bill")
    week_list = [Week(m, 450000 if m == last else 3000000) for m in MONDAYS]
    (move,) = of_kind(fixes([cause], [], gap=gap, week_list=week_list), "move_payment")
    assert move.date == date(2026, 12, 30)
    assert move.new_lowest_balance_cents == 550000


def test_no_gain_dropped() -> None:
    """C7: a fix that leaves the lowest where it was is not offered (AC 8)."""
    gap = gaps.Gap(
        starts_on=GAP_MONDAY,
        ends_on=date(2026, 11, 22),
        lowest_balance_cents=315000,
        lowest_week_starts_on=date(2026, 11, 16),
        shortfall_cents=185000,
    )
    week_list = weeks({GAP_MONDAY: 400000, date(2026, 11, 16): 315000})
    found = fixes([COASTAL], [], gap=gap, week_list=week_list)
    assert of_kind(found, "move_payment") == []
    assert [f.kind for f in found] == ["financing"]


def test_order() -> None:
    """C8: kind order, at most one of each, never both ways to borrow (AC 9)."""
    assert [f.kind for f in fixes([COASTAL, PAYROLL, BIRCH], [LINE])] == [
        "pay_early",
        "move_payment",
        "draw_credit",
    ]
    assert [f.kind for f in fixes([COASTAL, PAYROLL, BIRCH], [])] == [
        "pay_early",
        "move_payment",
        "financing",
    ]
    assert [f.kind for f in fixes([COASTAL], [])] == ["move_payment", "financing"]
