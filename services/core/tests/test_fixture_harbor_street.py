"""Spec 18: the Harbor Street Plumbing sample data. Pure; no database."""

import dataclasses
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, timedelta

import pytest

from app.fixtures import harbor_street
from app.fixtures.harbor_street import FutureItem, SampleBusiness, SampleTransaction
from app.modules.bank_sync.labels import business_days_between

MONTHS = [(2025 + (3 + i) // 12, (3 + i) % 12 + 1) for i in range(18)]
FIRST_DAY = date(2025, 3, 26)
LAST_DAY = date(2026, 9, 26)
TRANSFER_OUT = ("TRANSFER_OUT_ACCOUNT_TRANSFER", "TRANSFER_OUT_SAVINGS")
CARD_PAYMENT = "LOAN_PAYMENTS_CREDIT_CARD_PAYMENT"
CLIENTS_KNOWN = {"Acme Co", "Birch & Co"}


@pytest.fixture(scope="module")
def sample() -> SampleBusiness:
    return harbor_street.generate(0)


def _on(sample: SampleBusiness, account_key: str) -> list[SampleTransaction]:
    return [t for t in sample.history if t.account_key == account_key]


def _month(day: date) -> tuple[int, int]:
    return (day.year, day.month)


def _dump(value: SampleBusiness) -> str:
    return json.dumps(dataclasses.asdict(value), default=str, sort_keys=True)


def _clients(sample: SampleBusiness) -> list[SampleTransaction]:
    """Money in on Operating checking that is not a transfer: client payments."""
    return [
        t
        for t in _on(sample, "operating")
        if t.amount_cents > 0 and not (t.category_detailed or "").startswith("TRANSFER")
    ]


def test_same_seed_identical() -> None:
    """C1."""
    for seed in (0, 7):
        first, second = harbor_street.generate(seed), harbor_street.generate(seed)
        assert first == second
        assert _dump(first) == _dump(second)


def test_seeds_differ_only_in_history() -> None:
    """C2."""
    a, b = harbor_street.generate(0), harbor_street.generate(1)
    assert a.banks == b.banks
    assert a.expected_payments == b.expected_payments
    assert a.future == b.future
    amounts_a = [t.amount_cents for t in _clients(a)]
    amounts_b = [t.amount_cents for t in _clients(b)]
    assert amounts_a and amounts_b
    assert amounts_a != amounts_b


def test_business_identity(sample: SampleBusiness) -> None:
    """C3."""
    assert sample.business.name == "Harbor Street Plumbing"
    assert sample.business.province == "ON"
    assert sample.business.time_zone == "America/Toronto"


def test_banks_and_accounts(sample: SampleBusiness) -> None:
    """C4."""
    got = {
        (bank.institution_name, a.name): (
            a.type,
            a.mask,
            a.balance_cents,
            a.available_cents,
            a.currency,
        )
        for bank in sample.banks
        for a in bank.accounts
    }
    assert got == {
        ("Harbor Community Bank", "Operating checking"): (
            "checking",
            "2381",
            800000,
            None,
            "CAD",
        ),
        ("Harbor Community Bank", "Reserve savings"): (
            "savings",
            "9025",
            3430000,
            None,
            "CAD",
        ),
        ("Harbor Community Bank", "Line of credit"): (
            "line_of_credit",
            "7702",
            0,
            2000000,
            "CAD",
        ),
        ("Summit Federal", "Business Visa"): (
            "credit_card",
            "5530",
            245000,
            None,
            "CAD",
        ),
    }
    assert [b.institution_name for b in sample.banks] == [
        "Harbor Community Bank",
        "Summit Federal",
    ]


def test_history_span_and_types(sample: SampleBusiness) -> None:
    """C5."""
    assert sample.history
    for t in sample.history:
        assert FIRST_DAY <= t.date <= LAST_DAY
        assert type(t.amount_cents) is int
        assert t.amount_cents != 0
        assert t.currency == "CAD"
    assert min(t.date for t in sample.history) <= date(2025, 4, 1)
    keys = [t.key for t in sample.history]
    assert len(keys) == len(set(keys))


def test_payroll_schedule(sample: SampleBusiness) -> None:
    """C6."""
    payroll = [t for t in sample.history if t.counterparty == "Payroll"]
    assert {t.account_key for t in payroll} == {"operating"}
    assert {t.amount_cents for t in payroll} == {-1120000}
    fridays = []
    day = date(2026, 9, 18)
    while day >= FIRST_DAY:
        fridays.append(day)
        day -= timedelta(days=14)
    shifted = {
        date(2025, 4, 18): date(2025, 4, 17),
        date(2025, 12, 26): date(2025, 12, 24),
        date(2026, 4, 3): date(2026, 4, 2),
    }
    expected = sorted(shifted.get(d, d) for d in fridays)
    assert sorted(t.date for t in payroll) == expected


def _monthly(
    transactions: Iterable[SampleTransaction], description: str
) -> dict[tuple[int, int], list[SampleTransaction]]:
    by_month: dict[tuple[int, int], list[SampleTransaction]] = defaultdict(list)
    for t in transactions:
        if t.description == description:
            by_month[_month(t.date)].append(t)
    return by_month


def _day_rule(day_of_month: int, month: tuple[int, int]) -> date:
    """The day of month, or the next business day when it is not one."""
    from app.modules.bank_sync.labels import is_business_day

    day = date(month[0], month[1], day_of_month)
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def test_monthly_rent_and_software(sample: SampleBusiness) -> None:
    """C7."""
    operating = _on(sample, "operating")
    for description in ("Rent", "Software subscriptions"):
        by_month = _monthly(operating, description)
        assert sorted(by_month) == MONTHS
        assert all(len(rows) == 1 for rows in by_month.values())
        amounts = {rows[0].amount_cents for rows in by_month.values()}
        assert len(amounts) == 1 and amounts.pop() < 0
        # One rule for every month: the same nominal day, moved to the next business day.
        days = {rows[0].date.day for rows in by_month.values()}
        nominal = min(days)
        for month, rows in by_month.items():
            assert rows[0].date == _day_rule(nominal, month)


def test_suppliers_and_clients(sample: SampleBusiness) -> None:
    """C8."""
    coastal = [
        t
        for t in sample.history
        if t.counterparty == "Coastal Supply Co" and t.amount_cents < 0
    ]
    assert {_month(t.date) for t in coastal} >= set(MONTHS)
    assert all(t.amount_cents != -1450000 for t in coastal)
    clients = {t.counterparty for t in _clients(sample)}
    assert len(clients) >= 4
    assert clients >= CLIENTS_KNOWN


def test_card_payments_pair(sample: SampleBusiness) -> None:
    """C9."""
    visa = _on(sample, "visa")
    assert any(t.amount_cents < 0 for t in visa)
    card_in = [t for t in visa if t.amount_cents > 0]
    outs = [
        t
        for t in _on(sample, "operating")
        if t.category_detailed == CARD_PAYMENT and t.amount_cents < 0
    ]
    months = set()
    for out in outs:
        match = [
            t
            for t in card_in
            if t.amount_cents == -out.amount_cents
            and business_days_between(*sorted((out.date, t.date))) <= 3
        ]
        assert match, out
        months.add(_month(out.date))
    assert months >= set(MONTHS)


def test_monthly_transfers(sample: SampleBusiness) -> None:
    """C10."""
    operating = _on(sample, "operating")
    reserve = _on(sample, "reserve")
    months = set()
    for a in operating:
        for b in reserve:
            if a.date == b.date and a.amount_cents == -b.amount_cents:
                out = a if a.amount_cents < 0 else b
                if out.category_detailed in TRANSFER_OUT:
                    months.add(_month(a.date))
    assert months >= set(MONTHS)


@pytest.mark.parametrize("seed", range(10))
def test_balances_never_negative(seed: int) -> None:
    """C11."""
    sample = harbor_street.generate(seed)
    reference = {a.key: a.balance_cents for b in sample.banks for a in b.accounts}
    by_day: dict[tuple[str, date], int] = Counter()
    for t in sample.history:
        by_day[(t.account_key, t.date)] += t.amount_cents
    for key in ("operating", "reserve", "visa"):
        balance = reference[key]
        day = LAST_DAY
        while day >= FIRST_DAY:
            # `balance` is the end of `day`; for the card it is the amount owed.
            assert balance >= 0, (seed, key, day, balance)
            change = by_day.get((key, day), 0)
            balance = balance + change if key == "visa" else balance - change
            day -= timedelta(days=1)


# The reference future (S2).

MONDAYS = [date(2026, 9, 28) + timedelta(weeks=i) for i in range(13)]


def _week_ends(opening: int, items: Iterable[FutureItem]) -> list[int]:
    items = list(items)
    return [
        opening
        + sum(i.amount_cents for i in items if i.date <= start + timedelta(days=6))
        for start in MONDAYS
    ]


def _named(items: Iterable[FutureItem], name: str) -> list[FutureItem]:
    return [i for i in items if i.description.startswith(name)]


def test_future_expected_payments(sample: SampleBusiness) -> None:
    """C12."""
    got = [
        (p.description, p.amount_cents, p.currency, p.date, p.repeats, p.account_key)
        for p in sample.expected_payments
    ]
    assert got == [
        (
            "Acme Co, invoice 1042",
            800000,
            "CAD",
            date(2026, 10, 6),
            "once",
            "operating",
        ),
        (
            "Coastal Supply Co, quarterly order",
            -1450000,
            "CAD",
            date(2026, 11, 12),
            "every_3_months",
            "operating",
        ),
        (
            "Birch & Co, invoice 1057",
            960000,
            "CAD",
            date(2026, 11, 17),
            "once",
            "operating",
        ),
        (
            "Equipment lease deposit",
            -300000,
            "CAD",
            date(2026, 12, 7),
            "once",
            "operating",
        ),
    ]


def test_future_weeks_add_up(sample: SampleBusiness) -> None:
    """C13."""
    future = sample.future
    balances = {a.key: a.balance_cents for b in sample.banks for a in b.accounts}
    assert future.opening_cents == 4230000
    assert future.opening_cents == balances["operating"] + balances["reserve"]
    assert [w.start for w in future.weeks] == MONDAYS
    assert [w.end_cents for w in future.weeks] == _week_ends(
        future.opening_cents, future.items
    )
    assert all(date(2026, 9, 27) <= i.date <= date(2026, 12, 27) for i in future.items)


def test_future_gap_week_of_nov_9(sample: SampleBusiness) -> None:
    """C14."""
    ends = _week_ends(sample.future.opening_cents, sample.future.items)
    gap = MONDAYS.index(date(2026, 11, 9))
    assert ends[gap] == 315000
    assert all(end >= 1765000 for i, end in enumerate(ends) if i != gap)


def test_future_gap_causes(sample: SampleBusiness) -> None:
    """C15."""
    items = sample.future.items
    assert [(i.date, i.amount_cents) for i in _named(items, "Coastal Supply Co")] == [
        (date(2026, 11, 12), -1450000)
    ]
    assert (date(2026, 11, 13), -1120000) in [
        (i.date, i.amount_cents) for i in _named(items, "Payroll")
    ]
    assert [(i.date, i.amount_cents) for i in _named(items, "Birch & Co")] == [
        (date(2026, 11, 17), 960000)
    ]


def test_future_next_14_days(sample: SampleBusiness) -> None:
    """C16."""
    window = sorted(
        (i.date, i.amount_cents, i.description)
        for i in sample.future.items
        if date(2026, 9, 27) <= i.date <= date(2026, 10, 9)
    )
    assert len(window) == 4
    expected = [
        (date(2026, 10, 2), -1120000, "Payroll"),
        (date(2026, 10, 6), 800000, "Acme Co"),
        (date(2026, 10, 7), -64000, "Software subscriptions"),
        (date(2026, 10, 8), -245000, "Business Visa payment"),
    ]
    for (day, amount, description), (want_day, want_amount, want_name) in zip(
        window, expected, strict=True
    ):
        assert (day, amount) == (want_day, want_amount)
        assert description.startswith(want_name)


def _moved(items: Iterable[FutureItem], name: str, day: date) -> list[FutureItem]:
    return [
        dataclasses.replace(i, date=day) if i.description.startswith(name) else i
        for i in items
    ]


def test_future_three_fixes(sample: SampleBusiness) -> None:
    """C17."""
    future = sample.future
    items = list(future.items)
    draw = [
        *items,
        FutureItem(date=date(2026, 11, 9), amount_cents=200000, description="Draw"),
        FutureItem(date=date(2026, 11, 17), amount_cents=-200000, description="Repay"),
    ]
    cases = [
        (_moved(items, "Birch & Co", date(2026, 11, 10)), 1275000),
        (_moved(items, "Coastal Supply Co", date(2026, 11, 19)), 1765000),
        (draw, 515000),
    ]
    for edited, lowest in cases:
        assert min(_week_ends(future.opening_cents, edited)) == lowest


def test_future_continues_history(sample: SampleBusiness) -> None:
    """C18."""
    items = sample.future.items
    payroll = _named(items, "Payroll")
    assert [i.date for i in payroll] == [
        date(2026, 10, 2),
        date(2026, 10, 16),
        date(2026, 10, 30),
        date(2026, 11, 13),
        date(2026, 11, 27),
        date(2026, 12, 11),
        date(2026, 12, 24),
    ]
    assert {i.amount_cents for i in payroll} == {-1120000}
    operating = _on(sample, "operating")
    for description in ("Rent", "Software subscriptions"):
        history = [t for t in operating if t.description == description]
        nominal = min(t.date.day for t in history)
        future = _named(items, description)
        assert {i.amount_cents for i in future} == {history[0].amount_cents}
        months = sorted({_month(i.date) for i in future})
        assert months == [(2026, 10), (2026, 11), (2026, 12)]
        assert [i.date for i in sorted(future, key=lambda i: i.date)] == [
            _day_rule(nominal, m) for m in months
        ]
