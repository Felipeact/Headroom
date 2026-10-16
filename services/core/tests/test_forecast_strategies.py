"""Spec 21: the forecast strategies, as pure functions of hand-built inputs (AD-078)."""

import dataclasses
import uuid
from datetime import date, timedelta
from typing import Any

import pytest

from app.modules.forecasting import engine
from app.modules.forecasting.strategies import (
    STRATEGIES,
    CardAccount,
    CashAccount,
    ForecastInputs,
    ForecastResult,
    InputOccurrence,
    InputPattern,
    InputTransaction,
    ResultItem,
    history_weeks,
)

# A Saturday: week 1 starts on Monday 2026-09-28 and week 13 ends on 2026-12-27.
TODAY = date(2026, 9, 26)
WINDOW_END = date(2026, 12, 27)
CASH = uuid.UUID("00000000-0000-0000-0000-00000000000a")
SAVINGS = uuid.UUID("00000000-0000-0000-0000-00000000000b")
EXCLUDED = uuid.UUID("00000000-0000-0000-0000-00000000000c")
CARD = uuid.UUID("00000000-0000-0000-0000-00000000000d")
OPENING = 100_000

recurring = STRATEGIES["recurring_pattern"]
rolling = STRATEGIES["rolling_average"]
BOTH = pytest.mark.parametrize("strategy", ["recurring_pattern", "rolling_average"])


def inputs(today: date = TODAY, **changes: Any) -> ForecastInputs:
    base = ForecastInputs(
        today=today,
        week_starts=engine.week_starts(today),
        cash_accounts=(
            CashAccount(CASH, "CAD", OPENING),
            CashAccount(SAVINGS, "CAD", 0),
        ),
        card_accounts=(),
        transactions=(),
        patterns=(),
        open_occurrences=(),
        matched_transaction_ids=frozenset(),
    )
    return dataclasses.replace(base, **changes)


def txn(
    day: date,
    cents: int,
    account: uuid.UUID = CASH,
    label: str = "normal",
    linked: uuid.UUID | None = None,
    id: uuid.UUID | None = None,
) -> InputTransaction:
    return InputTransaction(
        id=id or uuid.uuid4(),
        account_id=account,
        date=day,
        amount_cents=cents,
        currency="CAD",
        label=label,
        linked_transaction_id=linked,
    )


def pattern(
    next_date: date,
    cents: int,
    schedule: str = "monthly",
    transactions: tuple[InputTransaction, ...] = (),
    account: uuid.UUID = CASH,
    name: str = "Rent",
) -> InputPattern:
    return InputPattern(
        id=uuid.uuid4(),
        account_id=account,
        amount_cents=cents,
        currency="CAD",
        description=name,
        counterparty=f"{name} Co",
        schedule=schedule,  # type: ignore[arg-type]  # tests pass valid words
        next_date=next_date,
        transaction_ids=tuple(t.id for t in transactions),
    )


def occurrence(
    day: date,
    cents: int,
    account: uuid.UUID = CASH,
    repeats: str | None = None,
    name: str = "Acme Co, invoice 1042",
) -> InputOccurrence:
    return InputOccurrence(
        expected_payment_id=uuid.uuid4(),
        account_id=account,
        amount_cents=cents,
        currency="CAD",
        description=name,
        date=day,
        repeats=repeats,  # type: ignore[arg-type]  # tests pass valid words
    )


def by_source(result: ForecastResult, source: str) -> list[ResultItem]:
    return [i for i in result.items if i.source == source]


def dated(items: list[ResultItem]) -> list[tuple[date, int]]:
    return sorted((i.date, i.amount_cents) for i in items)


def history(days: int) -> tuple[InputTransaction, ...]:
    """One normal transaction per day for `days` days before today, in and out."""
    return tuple(
        txn(TODAY - timedelta(days=n), 25_000 if n % 3 else -40_000)
        for n in range(1, days + 1)
    )


def biweekly_payroll() -> tuple[InputPattern, tuple[InputTransaction, ...]]:
    paid = tuple(
        txn(date(2026, 7, 10) + timedelta(days=14 * n), -1_120_000) for n in range(6)
    )
    return (
        pattern(date(2026, 10, 2), -1_120_000, "biweekly", paid, name="Payroll"),
        paid,
    )


def card_history(
    cash_account: uuid.UUID = CASH, latest_linked: bool = True
) -> tuple[InputTransaction, ...]:
    """Four card payments; the last 3 were on the 8th, 9th and 8th."""
    found: list[InputTransaction] = []
    for n, (day, cents) in enumerate(
        [
            (date(2026, 5, 8), 999_999),
            (date(2026, 6, 8), 250_000),
            (date(2026, 7, 9), 260_000),
            (date(2026, 8, 8), 270_000),
        ]
    ):
        cash_id, card_id = uuid.uuid4(), uuid.uuid4()
        linked = latest_linked or n < 3
        found.append(
            txn(
                day,
                -cents,
                cash_account,
                "card_payment",
                card_id if linked else None,
                cash_id,
            )
        )
        found.append(
            txn(day, cents, CARD, "card_payment", cash_id if linked else None, card_id)
        )
    return tuple(found)


def card(balance: int | None = 245_000) -> CardAccount:
    return CardAccount(CARD, "Business Visa", balance)


def rich_inputs() -> ForecastInputs:
    payroll, paid = biweekly_payroll()
    return inputs(
        card_accounts=(card(),),
        transactions=history(400) + paid + card_history(),
        patterns=(payroll,),
        open_occurrences=(
            occurrence(date(2026, 9, 20), 800_000),
            occurrence(date(2026, 11, 12), -1_450_000, repeats="quarterly"),
        ),
    )


# S1


@BOTH
def test_week_totals(strategy: str) -> None:
    """C3: weeks 1, 2 and 13 have items; week 3 has none."""
    result = STRATEGIES[strategy].forecast(
        inputs(
            open_occurrences=(
                occurrence(date(2026, 9, 30), 50_000),
                occurrence(date(2026, 10, 1), -20_000),
                occurrence(date(2026, 10, 6), -30_000),
                occurrence(date(2026, 12, 22), 10_000),
            )
        )
    )
    weeks = result.weeks
    assert [(w.money_in_cents, w.money_out_cents) for w in weeks[:3]] == [
        (50_000, -20_000),
        (0, -30_000),
        (0, 0),
    ]
    assert [w.end_balance_cents for w in weeks[:3]] == [130_000, 100_000, 100_000]
    assert (weeks[12].money_in_cents, weeks[12].money_out_cents) == (10_000, 0)
    assert (
        weeks[12].end_balance_cents == weeks[11].end_balance_cents + 10_000 == 110_000
    )
    previous = OPENING
    for w in weeks:
        assert w.money_out_cents <= 0 <= w.money_in_cents
        assert w.end_balance_cents == previous + w.money_in_cents + w.money_out_cents
        previous = w.end_balance_cents


@BOTH
def test_items_in_their_weeks(strategy: str) -> None:
    """C4: every item has an account, a date in the window and the week holding it."""
    given = rich_inputs()
    result = STRATEGIES[strategy].forecast(given)
    assert result.items
    starts = given.week_starts
    for item in result.items:
        assert isinstance(item.account_id, uuid.UUID)
        assert TODAY <= item.date <= WINDOW_END
        first = TODAY if item.week == 1 else starts[item.week - 1]
        assert first <= item.date <= starts[item.week - 1] + timedelta(days=6)
    for w in result.weeks:
        holds = [i for i in result.items if i.week == w.number]
        assert w.money_in_cents == sum(
            i.amount_cents for i in holds if i.amount_cents > 0
        )
        assert w.money_out_cents == sum(
            i.amount_cents for i in holds if i.amount_cents < 0
        )


@BOTH
@pytest.mark.parametrize("days", [0, 14, 730])
def test_history_lengths(strategy: str, days: int) -> None:
    """C5: no history, 2 weeks and 2 years each give 13 weeks without raising."""
    result = STRATEGIES[strategy].forecast(inputs(transactions=history(days)))
    assert [w.number for w in result.weeks] == list(range(1, 14))
    assert [w.starts_on for w in result.weeks] == list(engine.week_starts(TODAY))


@BOTH
def test_empty_is_flat(strategy: str) -> None:
    """C7."""
    result = STRATEGIES[strategy].forecast(inputs(card_accounts=(card(0),)))
    assert result.items == ()
    assert len(result.weeks) == 13
    for w in result.weeks:
        assert (w.end_balance_cents, w.low_cents, w.high_cents) == (OPENING,) * 3


# S2


def test_pattern_occurrences() -> None:
    """C12."""
    payroll, paid = biweekly_payroll()
    rent_paid = tuple(
        txn(d, -380_000)
        for d in [
            date(2026, 4, 15),
            date(2026, 5, 15),
            date(2026, 6, 15),
            date(2026, 7, 15),
            date(2026, 8, 17),
            date(2026, 9, 15),
        ]
    )
    rent = pattern(date(2026, 10, 15), -380_000, "monthly", rent_paid)
    result = recurring.forecast(
        inputs(transactions=paid + rent_paid, patterns=(payroll, rent))
    )
    items = by_source(result, "recurring_pattern")
    payroll_items = [i for i in items if i.source_id == payroll.id]
    assert [i.date for i in payroll_items] == [
        date(2026, 10, 2),
        date(2026, 10, 16),
        date(2026, 10, 30),
        date(2026, 11, 13),
        date(2026, 11, 27),
        date(2026, 12, 11),
    ]
    rent_items = [i for i in items if i.source_id == rent.id]
    assert [i.date for i in rent_items] == [
        date(2026, 10, 15),
        date(2026, 11, 16),
        date(2026, 12, 15),
    ]
    for i in rent_items:
        assert (i.amount_cents, i.description, i.counterparty, i.schedule) == (
            -380_000,
            "Rent",
            "Rent Co",
            "monthly",
        )
        assert (i.account_id, i.currency) == (CASH, "CAD")
    assert all(i.date <= WINDOW_END for i in items)


def test_late_pattern_today() -> None:
    """C13: next date 3 days before today."""
    paid = tuple(
        txn(date(2026, 7, 29) + timedelta(days=14 * n), -50_000) for n in range(4)
    )
    late = pattern(date(2026, 9, 23), -50_000, "biweekly", paid)
    result = recurring.forecast(inputs(transactions=paid, patterns=(late,)))
    assert [i.date for i in by_source(result, "recurring_pattern")] == [
        TODAY,
        date(2026, 10, 7),
        date(2026, 10, 21),
        date(2026, 11, 4),
        date(2026, 11, 18),
        date(2026, 12, 2),
        date(2026, 12, 16),
    ]


def dedup(
    rec: list[InputPattern], expected: list[InputOccurrence]
) -> tuple[list[ResultItem], list[ResultItem]]:
    result = recurring.forecast(
        inputs(patterns=tuple(rec), open_occurrences=tuple(expected))
    )
    return by_source(result, "expected_payment"), by_source(result, "recurring_pattern")


@pytest.mark.parametrize(
    ("cents", "day", "account", "dropped"),
    [
        (-109_000, date(2026, 11, 13), CASH, True),
        (-111_000, date(2026, 11, 13), CASH, False),
        (-100_000, date(2026, 11, 20), CASH, False),
        (100_000, date(2026, 11, 13), CASH, False),
        (-100_000, date(2026, 11, 13), SAVINGS, False),
    ],
)
def test_expected_wins_over_recurring(
    cents: int, day: date, account: uuid.UUID, dropped: bool
) -> None:
    """C16."""
    expected, rec = dedup(
        [pattern(day, cents, account=account)],
        [occurrence(date(2026, 11, 12), -100_000)],
    )
    assert dated(expected) == [(date(2026, 11, 12), -100_000)]
    assert dated(rec) == ([] if dropped else [(day, cents)])


def test_expected_wins_over_recurring_closest_and_once() -> None:
    """C16: the closer recurring item is dropped; each pairs at most once."""
    expected, rec = dedup(
        [
            pattern(date(2026, 11, 13), -100_000),
            pattern(date(2026, 11, 10), -100_000),
        ],
        [occurrence(date(2026, 11, 12), -100_000)],
    )
    assert dated(rec) == [(date(2026, 11, 10), -100_000)]
    assert len(expected) == 1

    expected, rec = dedup(
        [
            pattern(date(2026, 11, 13), -100_000),
            pattern(date(2026, 11, 20), -100_000),
        ],
        [
            occurrence(date(2026, 11, 12), -100_000),
            occurrence(date(2026, 11, 14), -100_000),
        ],
    )
    assert rec == []
    assert len(expected) == 2


def test_card_payments() -> None:
    """C17."""
    result = recurring.forecast(
        inputs(card_accounts=(card(),), transactions=card_history())
    )
    items = by_source(result, "card_payment")
    assert dated(items) == [
        (date(2026, 10, 8), -245_000),
        (date(2026, 11, 9), -260_000),
        (date(2026, 12, 8), -260_000),
    ]
    for i in items:
        assert (i.account_id, i.description, i.source_id) == (
            CASH,
            "Business Visa",
            CARD,
        )


def test_card_payment_edges() -> None:
    """C18."""
    unlinked = recurring.forecast(
        inputs(card_accounts=(card(),), transactions=card_history(latest_linked=False))
    )
    assert by_source(unlinked, "card_payment") == []

    excluded = recurring.forecast(
        inputs(card_accounts=(card(),), transactions=card_history(EXCLUDED))
    )
    assert by_source(excluded, "card_payment") == []

    for balance in (0, None):
        result = recurring.forecast(
            inputs(card_accounts=(card(balance),), transactions=card_history())
        )
        assert dated(by_source(result, "card_payment")) == [
            (date(2026, 11, 9), -260_000),
            (date(2026, 12, 8), -260_000),
        ]


def estimate_of(given: ForecastInputs) -> list[tuple[int, date, uuid.UUID, int]]:
    return sorted(
        (i.week, i.date, i.account_id, i.amount_cents)
        for i in by_source(recurring.forecast(given), "estimate")
    )


def test_estimate_window_and_exclusions() -> None:
    """C19: k is 13, so the window is today - 91 days to yesterday."""
    seeded = (
        txn(TODAY - timedelta(days=730), 1_000),
        txn(TODAY - timedelta(days=5), 130_000),
        txn(TODAY - timedelta(days=40), -65_000),
        txn(TODAY - timedelta(days=91), 26_000),
    )
    base = inputs(transactions=seeded)
    before = estimate_of(base)
    assert before

    in_pattern = txn(TODAY - timedelta(days=3), -13_000)
    matched = txn(TODAY - timedelta(days=3), 52_000)
    variants = [
        inputs(transactions=(*seeded, txn(TODAY, 13_000))),
        inputs(transactions=(*seeded, txn(TODAY - timedelta(days=92), 13_000))),
        inputs(
            transactions=(*seeded, in_pattern),
            patterns=(pattern(date(2027, 3, 1), -13_000, transactions=(in_pattern,)),),
        ),
        inputs(
            transactions=(*seeded, matched),
            matched_transaction_ids=frozenset({matched.id}),
        ),
        *(
            inputs(
                transactions=(
                    *seeded,
                    txn(TODAY - timedelta(days=3), 13_000, label=label),
                )
            )
            for label in ("internal_transfer", "in_transit", "card_payment")
        ),
        inputs(
            transactions=(*seeded, txn(TODAY - timedelta(days=3), 13_000, EXCLUDED))
        ),
    ]
    for variant in variants:
        assert estimate_of(variant) == before

    changed = inputs(transactions=(*seeded, txn(TODAY - timedelta(days=1), 13_000)))
    assert estimate_of(changed) != before


def test_estimate_k_and_amounts() -> None:
    """C20."""
    for days, k in ((3, 1), (14, 2), (730, 13)):
        assert (
            history_weeks(inputs(transactions=(txn(TODAY - timedelta(days=days), 1),)))
            == k
        )
    assert by_source(recurring.forecast(inputs()), "estimate") == []

    given = inputs(
        transactions=(
            txn(TODAY - timedelta(days=14), 100_000),
            txn(TODAY - timedelta(days=3), 200_001),
            txn(TODAY - timedelta(days=10), -300_003),
        )
    )
    estimates = by_source(recurring.forecast(given), "estimate")
    for week in range(1, 14):
        here = [i for i in estimates if i.week == week]
        assert sorted((i.account_id, i.amount_cents) for i in here) == [
            (CASH, -150_002),
            (CASH, 150_000),
        ]


def test_estimate_item_shape() -> None:
    """C21."""
    given = inputs(transactions=(txn(TODAY - timedelta(days=20), 70_000),))
    estimates = by_source(recurring.forecast(given), "estimate")
    assert len(estimates) == 13
    assert [i.date for i in estimates] == [TODAY, *given.week_starts[1:]]
    for i in estimates:
        assert (i.description, i.counterparty, i.schedule, i.source_id) == (None,) * 4
        assert i.amount_cents > 0

    monday = date(2026, 9, 28)
    on_monday = inputs(monday, transactions=(txn(monday - timedelta(days=20), 70_000),))
    estimates = by_source(recurring.forecast(on_monday), "estimate")
    assert estimates[0].date == monday == on_monday.week_starts[0]


def band_history(extra: tuple[InputTransaction, ...] = ()) -> ForecastInputs:
    """Weekly net estimate totals of 100000, 300000, 200000 and 400000 (k = 4)."""
    return inputs(
        transactions=(
            txn(TODAY - timedelta(days=1), 100_000),
            txn(TODAY - timedelta(days=8), 300_000),
            txn(TODAY - timedelta(days=15), 200_000),
            txn(TODAY - timedelta(days=28), 400_000),
            *extra,
        )
    )


def half_widths(result: ForecastResult) -> list[int]:
    widths = []
    for w in result.weeks:
        assert w.end_balance_cents - w.low_cents == w.high_cents - w.end_balance_cents
        widths.append(w.high_cents - w.end_balance_cents)
    return widths


def test_band() -> None:
    """C22."""
    widths = half_widths(recurring.forecast(band_history()))
    assert widths[0] == 111_803
    assert widths[12] == 403_113
    flat = recurring.forecast(
        inputs(transactions=(txn(TODAY - timedelta(days=3), 5_000),))
    )
    assert half_widths(flat) == [0] * 13


# S3


def test_rolling_average_items() -> None:
    """C24: k is 13; in = (130000 + 26000) / 13, out = (-260000 - 13000 - 39000) / 13."""
    day = TODAY - timedelta(days=10)
    in_pattern = txn(day, -39_000)
    matched = txn(day, 77_777)
    cash_side, card_side = uuid.uuid4(), uuid.uuid4()
    given = inputs(
        card_accounts=(card(),),
        transactions=(
            txn(TODAY - timedelta(days=730), 1_000, EXCLUDED),
            txn(TODAY - timedelta(days=700), 0, CASH, "internal_transfer"),
            txn(day, 130_000),
            txn(day, -260_000, CASH, "card_payment", card_side, cash_side),
            txn(day, 260_000, CARD, "card_payment", cash_side, card_side),
            txn(day, 26_000, CASH, "credit_draw"),
            txn(day, -13_000, CASH, "credit_repayment"),
            txn(day, 999_999, CASH, "internal_transfer"),
            txn(day, -55_555, CASH, "in_transit"),
            matched,
            in_pattern,
        ),
        patterns=(pattern(date(2026, 10, 15), -39_000, transactions=(in_pattern,)),),
        open_occurrences=(occurrence(date(2026, 10, 6), 800_000),),
        matched_transaction_ids=frozenset({matched.id}),
    )
    result = rolling.forecast(given)
    assert by_source(result, "recurring_pattern") == []
    assert by_source(result, "card_payment") == []
    assert dated(by_source(result, "expected_payment")) == [
        (date(2026, 10, 6), 800_000)
    ]
    estimates = by_source(result, "estimate")
    for week in range(1, 14):
        assert sorted(
            (i.account_id, i.amount_cents) for i in estimates if i.week == week
        ) == [(CASH, -24_000), (CASH, 12_000)]


def test_rolling_average_band() -> None:
    """C25."""
    weekly_card = tuple(
        txn(TODAY - timedelta(days=d), -50_000, label="card_payment")
        for d in (2, 9, 16, 23)
    )
    shifted = rolling.forecast(band_history(weekly_card))
    assert half_widths(shifted)[0] == 111_803

    varying = band_history(
        (txn(TODAY - timedelta(days=2), -100_000, label="card_payment"),)
    )
    assert (
        half_widths(rolling.forecast(varying))[0]
        != half_widths(recurring.forecast(varying))[0]
    )
    assert half_widths(recurring.forecast(varying))[0] == 111_803


# S4


def test_holiday_rule() -> None:
    """C33."""
    payroll, paid = biweekly_payroll()
    software_paid = tuple(
        txn(d, -64_000)
        for d in [
            date(2026, 4, 7),
            date(2026, 5, 7),
            date(2026, 6, 8),
            date(2026, 7, 7),
            date(2026, 8, 7),
            date(2026, 9, 7),
        ]
    )
    software = pattern(date(2026, 10, 7), -64_000, "monthly", software_paid)
    result = recurring.forecast(
        inputs(transactions=paid + software_paid, patterns=(payroll, software))
    )
    dates = {i.date for i in by_source(result, "recurring_pattern")}
    assert not dates & {date(2026, 12, 24), date(2026, 12, 25), date(2026, 12, 29)}
    assert max(i.date for i in result.items if i.source_id == payroll.id) == date(
        2026, 12, 11
    )
    assert [i.date for i in result.items if i.source_id == software.id] == [
        date(2026, 10, 7),
        date(2026, 11, 9),
        date(2026, 12, 7),
    ]
