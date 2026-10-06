"""Spec 19: the recurring payment detector, on synthetic transactions only."""

import random
import uuid
from collections.abc import Sequence
from datetime import date, timedelta

import pytest

from app.modules.bank_sync.service import TransactionView
from app.modules.forecasting import detection
from app.modules.forecasting.detection import DetectedPattern

ACCOUNT = uuid.uuid4()
OTHER_ACCOUNT = uuid.uuid4()


def tx(
    day: date,
    amount_cents: int = -380_000,
    *,
    counterparty: str | None = "Wharfside Properties",
    description: str = "Rent",
    account_id: uuid.UUID = ACCOUNT,
    currency: str = "CAD",
    label: str = "normal",
    pending: bool = False,
) -> TransactionView:
    return TransactionView(
        id=uuid.uuid4(),
        account_id=account_id,
        date=day,
        amount_cents=amount_cents,
        currency=currency,
        pending=pending,
        description=description,
        counterparty=counterparty,
        label=label,
    )


def months(first: tuple[int, int], count: int, day: int) -> list[date]:
    """`day` of `count` consecutive months from `first`."""
    year, month = first
    result = []
    for _ in range(count):
        result.append(date(year, month, day))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return result


def series(days: Sequence[date], **kwargs: object) -> list[TransactionView]:
    return [tx(d, **kwargs) for d in days]  # type: ignore[arg-type]


def one_off(day: date) -> TransactionView:
    """An unrelated transaction that moves the as-of day."""
    return tx(day, 12_345, counterparty="One-off client", description="One-off")


def only(patterns: list[DetectedPattern]) -> DetectedPattern:
    assert len(patterns) == 1, patterns
    return patterns[0]


WEEKLY = [date(2026, 6, 2) + timedelta(days=7 * n) for n in range(8)]
BIWEEKLY = [date(2026, 4, 3) + timedelta(days=14 * n) for n in range(8)]
SEMIMONTHLY = sorted(months((2026, 3), 6, 1) + months((2026, 3), 6, 15))
MONTHLY = months((2026, 1), 8, 15)
QUARTERLY = [
    date(2025, 1, 10),
    date(2025, 4, 10),
    date(2025, 7, 10),
    date(2025, 10, 10),
    date(2026, 1, 10),
]
SCHEDULES: dict[str, list[date]] = {
    "weekly": WEEKLY,
    "biweekly": BIWEEKLY,
    "semimonthly": SEMIMONTHLY,
    "monthly": MONTHLY,
    "quarterly": QUARTERLY,
}
TOLERANCE = {"weekly": 1, "biweekly": 3, "semimonthly": 3, "monthly": 4, "quarterly": 7}
HALF_INTERVAL = {
    "weekly": 3,
    "biweekly": 7,
    "semimonthly": 7,
    "monthly": 15,
    "quarterly": 45,
}


@pytest.mark.parametrize(
    ("label", "pending"),
    [
        ("card_purchase", False),
        ("card_payment", False),
        ("internal_transfer", False),
        ("in_transit", False),
        ("credit_draw", False),
        ("credit_repayment", False),
        ("normal", True),
    ],
)
def test_only_normal_posted_excluded(label: str, pending: bool) -> None:
    """C1: these transactions are never in a pattern."""
    days = months((2026, 1), 6, 15)
    assert detection.detect(series(days, label=label, pending=pending)) == []


def test_only_normal_posted_included() -> None:
    """C1: the same series, normal and posted, is one pattern."""
    only(detection.detect(series(months((2026, 1), 6, 15))))


def test_grouping_key_counterparty_normalised() -> None:
    """C2: case and surrounding spaces don't split a counterparty."""
    days = months((2025, 10), 12, 15)
    transactions = [
        tx(
            d,
            counterparty="Wharfside Properties"
            if n % 2 == 0
            else "  WHARFSIDE properties ",
        )
        for n, d in enumerate(days)
    ]
    assert len(only(detection.detect(transactions)).transaction_ids) == 12


@pytest.mark.parametrize(
    "second",
    [
        {"account_id": OTHER_ACCOUNT},
        {"amount_cents": 50_000},
        {"currency": "USD"},
    ],
    ids=["account", "direction", "currency"],
)
def test_grouping_key_splits(second: dict[str, object]) -> None:
    """C2: account, direction and currency each make a separate pattern."""
    days = months((2026, 1), 6, 15)
    transactions = series(days, amount_cents=-50_000) + series(
        days, **{"amount_cents": -50_000, **second}
    )
    assert len(detection.detect(transactions)) == 2


def test_grouping_key_description_fallback() -> None:
    """C2: a null counterparty groups by description without digits."""
    days = months((2026, 1), 6, 15)
    transactions = [
        tx(d, counterparty=None, description=f"Invoice {1001 + n}")
        for n, d in enumerate(days)
    ]
    pattern = only(detection.detect(transactions))
    assert pattern.counterparty == "Invoice 1006"
    assert len(pattern.transaction_ids) == 6


def test_amount_bands_within() -> None:
    """C3: 115% of the band's smallest amount is still the same band."""
    days = months((2026, 1), 6, 15)
    transactions = series(days[:3], amount_cents=-100_000) + series(
        days[3:], amount_cents=-115_000
    )
    assert len(only(detection.detect(transactions)).transaction_ids) == 6


def test_amount_bands_split() -> None:
    """C3: one cent more starts a new band; the old one has stopped."""
    days = months((2026, 1), 6, 15)
    later = series(days[3:], amount_cents=-115_001)
    transactions = series(days[:3], amount_cents=-100_000) + later
    pattern = only(detection.detect(transactions))
    assert pattern.amount_cents == -115_001
    assert pattern.transaction_ids == tuple(t.id for t in later)


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_each_schedule(schedule: str) -> None:
    """C4."""
    transactions = series(SCHEDULES[schedule])
    pattern = only(detection.detect(transactions))
    assert pattern.schedule == schedule
    assert pattern.transaction_ids == tuple(t.id for t in transactions)


@pytest.mark.parametrize("schedule", SCHEDULES)
@pytest.mark.parametrize("extra", [0, 1])
def test_tolerance_edges(schedule: str, extra: int) -> None:
    """C5: the 5th date moved later by the tolerance is a hit; one day more is not."""
    days = list(SCHEDULES[schedule])
    days[4] += timedelta(days=TOLERANCE[schedule] + extra)
    transactions = series(days)
    pattern = only(detection.detect(transactions))
    assert pattern.schedule == schedule
    ids = [t.id for t in transactions]
    if extra:
        assert transactions[4].id not in pattern.transaction_ids
        assert len(pattern.transaction_ids) == len(ids) - 1
    else:
        assert pattern.transaction_ids == tuple(ids)


def nine_of_twelve() -> list[TransactionView]:
    days = months((2025, 10), 12, 15)
    return series([d for n, d in enumerate(days) if n not in (2, 5, 8)])


def test_share_threshold() -> None:
    """C6, C10: 9 of 12 expected dates hit is 75% and fits, with confidence 75."""
    pattern = only(detection.detect(nine_of_twelve()))
    assert pattern.schedule == "monthly"
    assert pattern.confidence == 75


def test_share_threshold_below() -> None:
    """C6: 8 of 12 does not fit."""
    days = months((2025, 10), 12, 15)
    kept = [d for n, d in enumerate(days) if n not in (2, 5, 7, 9)]
    assert len(kept) == 8 and kept[0] == days[0] and kept[-1] == days[-1]
    assert detection.detect(series(kept)) == []


@pytest.mark.parametrize(
    "days",
    [
        [date(2025, 9, 17), date(2026, 3, 17), date(2026, 6, 17)],
        [date(2026, 1, 15), date(2026, 2, 15), date(2026, 4, 15)],
    ],
    ids=["quarterly-gap", "monthly-gap"],
)
def test_three_hits_need_no_gap(days: list[date]) -> None:
    """AC 4 (amended): 3 hits with a missed expected date are not a pattern."""
    assert detection.detect(series(days)) == []


def test_three_needed() -> None:
    """C7: twice is not recurring; three times is, with confidence 50."""
    assert detection.detect(series(months((2026, 1), 2, 15))) == []
    pattern = only(detection.detect(series(months((2026, 1), 3, 15))))
    assert pattern.schedule == "monthly"
    assert pattern.confidence == 50


def test_next_date_biweekly_cadence() -> None:
    """C8: a last payment moved a day earlier doesn't move the cadence."""
    days = list(BIWEEKLY)
    days[-1] -= timedelta(days=1)
    assert days[-1].weekday() == 3
    pattern = only(detection.detect(series(days)))
    assert pattern.next_date == BIWEEKLY[-1] + timedelta(days=14)


def test_next_date_month_end_clamped_and_moved() -> None:
    """C8: day 31 in February is Feb 28, a Saturday, so Monday Mar 2."""
    days = [
        date(2025, 8, 31),
        date(2025, 9, 30),
        date(2025, 10, 31),
        date(2025, 11, 30),
        date(2025, 12, 31),
        date(2026, 1, 31),
    ]
    pattern = only(detection.detect(series(days)))
    assert pattern.schedule == "monthly"
    assert pattern.next_date == date(2026, 3, 2)


def test_next_date_weekend_moved_forward() -> None:
    """C8: Aug 15, 2026 is a Saturday."""
    pattern = only(detection.detect(series(months((2026, 3), 5, 15))))
    assert pattern.next_date == date(2026, 8, 17)


def test_median_amount_last_six() -> None:
    """C9: the median of the last 6, -100002.5, rounds half to even."""
    amounts = [
        -90_000,
        -90_000,
        -100_000,
        -100_001,
        -100_002,
        -100_003,
        -100_004,
        -100_005,
    ]
    days = months((2026, 1), 8, 15)
    transactions = [tx(d, a) for d, a in zip(days, amounts, strict=True)]
    assert only(detection.detect(transactions)).amount_cents == -100_002


def test_median_amount_three() -> None:
    """C9."""
    days = months((2026, 1), 3, 15)
    transactions = [
        tx(d, a) for d, a in zip(days, [-100_000, -100_003, -100_001], strict=True)
    ]
    assert only(detection.detect(transactions)).amount_cents == -100_001


@pytest.mark.parametrize(
    ("count", "confidence"), [(3, 50), (4, 67), (6, 100), (12, 100)]
)
def test_confidence(count: int, confidence: int) -> None:
    """C10."""
    pattern = only(detection.detect(series(months((2025, 10), count, 15))))
    assert pattern.confidence == confidence


@pytest.mark.parametrize("schedule", SCHEDULES)
def test_stopped(schedule: str) -> None:
    """C11: reported up to half an interval past its next date, not one day later."""
    transactions = series(SCHEDULES[schedule])
    next_date = only(detection.detect(transactions)).next_date
    edge = next_date + timedelta(days=HALF_INTERVAL[schedule])
    kept = detection.detect([*transactions, one_off(edge)])
    assert [p.schedule for p in kept] == [schedule]
    late = detection.detect([*transactions, one_off(edge + timedelta(days=1))])
    assert late == []


def test_pattern_fields() -> None:
    """C12: names from the most recent hit; only hits, oldest first."""
    days = months((2026, 1), 6, 15)
    transactions = [
        tx(
            d,
            counterparty="WHARFSIDE PROPERTIES" if n < 5 else "Wharfside Properties",
            description=f"Rent {n + 1}",
        )
        for n, d in enumerate(days)
    ]
    extra = tx(date(2026, 3, 1), counterparty="Wharfside Properties")
    pattern = only(detection.detect([extra, *reversed(transactions)]))
    assert pattern.counterparty == "Wharfside Properties"
    assert pattern.description == "Rent 6"
    assert pattern.account_id == ACCOUNT
    assert pattern.currency == "CAD"
    assert pattern.transaction_ids == tuple(t.id for t in transactions)
    assert extra.id not in pattern.transaction_ids


def test_input_order() -> None:
    """C13: any order of the same transactions gives the same patterns."""
    transactions = [
        t
        for name, days in SCHEDULES.items()
        for t in series(days, counterparty=name, description=name)
    ]
    transactions += [
        tx(d, counterparty="Wharfside Properties", description=f"Rent {n}")
        for n, d in enumerate(months((2026, 1), 6, 20))
    ]
    transactions.append(tx(date(2026, 3, 1), counterparty="Wharfside Properties"))
    expected = detection.detect(transactions)
    assert expected
    for n in range(5):
        shuffled = list(transactions)
        random.Random(n).shuffle(shuffled)
        assert detection.detect(shuffled) == expected
