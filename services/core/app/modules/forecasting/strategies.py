"""Forecast strategies (spec 21 door 2, AD-078): 13 weeks from a business's inputs.

A strategy is a pure function of `ForecastInputs`: no session and no clock, so spec 22's
backtest can replay what was known on an earlier day. Amounts are integer cents in our
sign: money in positive, money out negative. To add a method, write a class with a
`name` and a `forecast` method and `register` it; `FORECAST_STRATEGY` selects one.
"""

import calendar
import math
import uuid
from collections import defaultdict
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median_low, pstdev
from typing import ClassVar, Protocol

from app.modules.bank_sync.service import is_business_day
from app.modules.forecasting import detection
from app.modules.forecasting.models import ItemSource, Repeats, Schedule

WEEKS = 13
# v1 counts only Canadian dollars as cash (AGENTS.md).
CASH_CURRENCY = "CAD"
# The estimate looks back at most this many weeks (AC 11).
MAX_HISTORY_WEEKS = 13
# An expected and a recurring item are one payment within these limits (AC 9).
SAME_PAYMENT_DAYS = 7
SAME_PAYMENT_PERCENT = 10
CARD_PAYMENTS_AVERAGED = 3
# Labels the fallback leaves out of its estimate (AC 14).
NOT_SPENDING = ("internal_transfer", "in_transit")


@dataclass(frozen=True)
class CashAccount:
    """An included account; only the CAD ones count as cash."""

    id: uuid.UUID
    currency: str
    balance_cents: int | None


@dataclass(frozen=True)
class CardAccount:
    id: uuid.UUID
    name: str
    # The amount owed, as the bank reports it.
    balance_cents: int | None


@dataclass(frozen=True)
class InputTransaction:
    id: uuid.UUID
    account_id: uuid.UUID
    date: date
    amount_cents: int
    currency: str
    label: str
    linked_transaction_id: uuid.UUID | None


@dataclass(frozen=True)
class InputPattern:
    # Not part of the fingerprint: a refresh gives the same pattern a new ID (AD-071).
    id: uuid.UUID
    account_id: uuid.UUID
    amount_cents: int
    currency: str
    description: str
    counterparty: str
    schedule: Schedule
    next_date: date
    transaction_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class InputOccurrence:
    expected_payment_id: uuid.UUID
    account_id: uuid.UUID
    amount_cents: int
    currency: str
    description: str
    date: date
    repeats: Repeats | None


@dataclass(frozen=True)
class ForecastInputs:
    # Business-local (door 6).
    today: date
    # The 13 Mondays.
    week_starts: tuple[date, ...]
    cash_accounts: tuple[CashAccount, ...]
    card_accounts: tuple[CardAccount, ...]
    transactions: tuple[InputTransaction, ...]
    patterns: tuple[InputPattern, ...]
    open_occurrences: tuple[InputOccurrence, ...]
    # Transactions matched to an expected payment occurrence (AD-074).
    matched_transaction_ids: frozenset[uuid.UUID]


@dataclass(frozen=True)
class ResultItem:
    week: int
    date: date
    account_id: uuid.UUID
    amount_cents: int
    currency: str
    source: ItemSource
    source_id: uuid.UUID | None
    description: str | None
    counterparty: str | None
    schedule: str | None


@dataclass(frozen=True)
class ResultWeek:
    number: int
    starts_on: date
    end_balance_cents: int
    low_cents: int
    high_cents: int
    money_in_cents: int
    money_out_cents: int


@dataclass(frozen=True)
class ForecastResult:
    items: tuple[ResultItem, ...]
    weeks: tuple[ResultWeek, ...]


class ForecastStrategy(Protocol):
    name: ClassVar[str]

    def forecast(self, inputs: ForecastInputs) -> ForecastResult: ...


STRATEGIES: dict[str, ForecastStrategy] = {}


def register(strategy: ForecastStrategy) -> None:
    """Make `strategy` selectable by its name."""
    STRATEGIES[strategy.name] = strategy


def opening_balance(inputs: ForecastInputs) -> int:
    """The sum of the cash accounts' balances; a null balance counts as 0 (AC 2)."""
    return sum(
        a.balance_cents or 0
        for a in inputs.cash_accounts
        if a.currency == CASH_CURRENCY
    )


def window_end(inputs: ForecastInputs) -> date:
    """The Sunday that ends week 13."""
    return inputs.week_starts[-1] + timedelta(days=6)


def week_of(inputs: ForecastInputs, day: date) -> int:
    """The week holding `day`; week 1 also holds today to its Monday (door 6)."""
    if day < inputs.week_starts[0]:
        return 1
    return (day - inputs.week_starts[0]).days // 7 + 1


def round_div(numerator: int, denominator: int) -> int:
    """`numerator / denominator` rounded half to even, in integers."""
    quotient, remainder = divmod(numerator, denominator)
    if 2 * remainder > denominator or (2 * remainder == denominator and quotient % 2):
        quotient += 1
    return quotient


def _cash_ids(inputs: ForecastInputs) -> set[uuid.UUID]:
    return {a.id for a in inputs.cash_accounts if a.currency == CASH_CURRENCY}


def _next_business_day(day: date) -> date:
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def _item(
    inputs: ForecastInputs,
    day: date,
    account_id: uuid.UUID,
    amount_cents: int,
    source: ItemSource,
    source_id: uuid.UUID | None = None,
    description: str | None = None,
    counterparty: str | None = None,
    schedule: str | None = None,
) -> ResultItem:
    # Late money is still coming: it is dated today, never skipped (AC 7, AC 8).
    day = max(day, inputs.today)
    return ResultItem(
        week=week_of(inputs, day),
        date=day,
        account_id=account_id,
        amount_cents=amount_cents,
        currency=CASH_CURRENCY,
        source=source,
        source_id=source_id,
        description=description,
        counterparty=counterparty,
        schedule=schedule,
    )


def expected_items(inputs: ForecastInputs) -> list[ResultItem]:
    """One item per open occurrence on a cash account (AC 8)."""
    cash, end = _cash_ids(inputs), window_end(inputs)
    return [
        _item(
            inputs,
            o.date,
            o.account_id,
            o.amount_cents,
            "expected_payment",
            source_id=o.expected_payment_id,
            description=o.description,
            schedule=o.repeats,
        )
        for o in inputs.open_occurrences
        if o.account_id in cash and o.date <= end
    ]


def _pattern_items(inputs: ForecastInputs) -> list[ResultItem]:
    """Each pattern's occurrences from its next date to the window end (AC 7)."""
    cash, end = _cash_ids(inputs), window_end(inputs)
    dates = {t.id: t.date for t in inputs.transactions}
    items = []
    for p in inputs.patterns:
        if p.account_id not in cash or p.next_date > end:
            continue
        days = sorted(dates[t] for t in p.transaction_ids if t in dates)
        found = [p.next_date]
        if days:
            for day in detection.later_dates(p.schedule, days, p.next_date):
                if day > end:
                    break
                found.append(day)
        items += [
            _item(
                inputs,
                day,
                p.account_id,
                p.amount_cents,
                "recurring_pattern",
                source_id=p.id,
                description=p.description,
                counterparty=p.counterparty,
                schedule=p.schedule,
            )
            for day in found
        ]
    return items


def _same_payment(expected: ResultItem, recurring: ResultItem) -> bool:
    exp, rec = expected.amount_cents, recurring.amount_cents
    return (
        expected.account_id == recurring.account_id
        and (exp > 0) == (rec > 0)
        and 100 * abs(rec - exp) <= SAME_PAYMENT_PERCENT * abs(exp)
        and abs((expected.date - recurring.date).days) <= SAME_PAYMENT_DAYS
    )


def _without_duplicates(
    expected: list[ResultItem], recurring: list[ResultItem]
) -> list[ResultItem]:
    """The recurring items no expected item stands for; the owner's entry wins (AC 9)."""
    pairs = sorted(
        (
            (
                e.date,
                abs((e.date - r.date).days),
                str(e.source_id),
                str(r.source_id),
                r.date,
                i,
                j,
            )
            for i, e in enumerate(expected)
            for j, r in enumerate(recurring)
            if _same_payment(e, r)
        ),
    )
    used_expected: set[int] = set()
    dropped: set[int] = set()
    for *_, i, j in pairs:
        if i not in used_expected and j not in dropped:
            used_expected.add(i)
            dropped.add(j)
    return [r for j, r in enumerate(recurring) if j not in dropped]


def _on_day(year: int, month: int, day_of_month: int) -> date:
    return date(year, month, min(day_of_month, calendar.monthrange(year, month)[1]))


def _months_from(day: date) -> Iterator[tuple[int, int]]:
    year, month = day.year, day.month
    while True:
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def _card_items(inputs: ForecastInputs) -> list[ResultItem]:
    """Each card's payments from the cash account that pays it (AC 10)."""
    cash, end = _cash_ids(inputs), window_end(inputs)
    by_id = {t.id: t for t in inputs.transactions}
    items = []
    for card in inputs.card_accounts:
        card_side = sorted(
            (
                t
                for t in inputs.transactions
                if t.account_id == card.id and t.label == "card_payment"
            ),
            key=lambda t: (t.date, t.id),
        )
        if not card_side or card_side[-1].linked_transaction_id not in by_id:
            continue
        paid_from = by_id[card_side[-1].linked_transaction_id]
        if paid_from.account_id not in cash:
            continue
        payments = [
            by_id[t.linked_transaction_id]
            for t in card_side
            if t.linked_transaction_id in by_id
        ][-CARD_PAYMENTS_AVERAGED:]
        day_of_month = median_low(p.date.day for p in payments)
        average = round_div(sum(abs(p.amount_cents) for p in payments), len(payments))
        months = _months_from(inputs.today)
        days = (_on_day(*month, day_of_month) for month in months)
        first = next(days)
        if first < inputs.today:
            first = next(days)
        # The first payment clears today's balance; later ones are typical months.
        due: list[tuple[date, int]] = []
        if card.balance_cents is not None and card.balance_cents > 0:
            due.append((_next_business_day(first), -card.balance_cents))
        for later in days:
            day = _next_business_day(later)
            if day > end:
                break
            due.append((day, -average))
        items += [
            _item(
                inputs,
                day,
                paid_from.account_id,
                cents,
                "card_payment",
                source_id=card.id,
                description=card.name,
            )
            for day, cents in due
            if day <= end and cents != 0
        ]
    return items


def history_weeks(inputs: ForecastInputs) -> int:
    """`k`: the whole or part weeks since the oldest cash-account transaction, 1 to 13."""
    cash = _cash_ids(inputs)
    days = [t.date for t in inputs.transactions if t.account_id in cash]
    if not days:
        return 1
    weeks = math.ceil((inputs.today - min(days)).days / 7)
    return max(1, min(MAX_HISTORY_WEEKS, weeks))


def _estimate(
    inputs: ForecastInputs, counts: Callable[[InputTransaction], bool]
) -> tuple[list[ResultItem], float]:
    """Weekly averages of the counted cash-account transactions of the last k weeks.

    Returns the estimate items (AC 11) and σ, the population standard deviation of the
    k weekly net totals (AC 12).
    """
    cash = _cash_ids(inputs)
    k = history_weeks(inputs)
    first = inputs.today - timedelta(days=7 * k)
    yesterday = inputs.today - timedelta(days=1)
    totals: dict[tuple[uuid.UUID, bool], int] = defaultdict(int)
    blocks = [0] * k
    for t in inputs.transactions:
        if (
            t.account_id in cash
            and first <= t.date <= yesterday
            and t.id not in inputs.matched_transaction_ids
            and counts(t)
        ):
            totals[(t.account_id, t.amount_cents > 0)] += t.amount_cents
            blocks[(yesterday - t.date).days // 7] += t.amount_cents
    items = []
    for number, monday in enumerate(inputs.week_starts, start=1):
        day = inputs.today if number == 1 else monday
        for (account_id, _), total in sorted(
            totals.items(), key=lambda kv: (str(kv[0][0]), kv[0][1])
        ):
            amount = round_div(total, k)
            if amount != 0:
                items.append(_item(inputs, day, account_id, amount, "estimate"))
    return items, pstdev(blocks) if k > 1 else 0.0


def weeks_of(
    inputs: ForecastInputs, items: Iterable[ResultItem], sigma: float
) -> tuple[ResultWeek, ...]:
    """Each week's money in and out, end balance and band (AC 3, AC 12)."""
    money_in = [0] * WEEKS
    money_out = [0] * WEEKS
    for item in items:
        if item.amount_cents > 0:
            money_in[item.week - 1] += item.amount_cents
        else:
            money_out[item.week - 1] += item.amount_cents
    balance = opening_balance(inputs)
    weeks = []
    for n, monday in enumerate(inputs.week_starts, start=1):
        balance += money_in[n - 1] + money_out[n - 1]
        half = round(sigma * math.sqrt(n))
        weeks.append(
            ResultWeek(
                number=n,
                starts_on=monday,
                end_balance_cents=balance,
                low_cents=balance - half,
                high_cents=balance + half,
                money_in_cents=money_in[n - 1],
                money_out_cents=money_out[n - 1],
            )
        )
    return tuple(weeks)


def _result(
    inputs: ForecastInputs, items: list[ResultItem], sigma: float
) -> ForecastResult:
    ordered = sorted(
        items,
        key=lambda i: (
            i.date,
            i.source,
            str(i.source_id),
            str(i.account_id),
            i.amount_cents,
        ),
    )
    return ForecastResult(tuple(ordered), weeks_of(inputs, ordered, sigma))


class RecurringPatternStrategy:
    """Named payments (patterns, expected payments, card payments) plus an estimate of
    the rest: the recent `normal` transactions none of them explains (AC 7-12)."""

    name: ClassVar[str] = "recurring_pattern"

    def forecast(self, inputs: ForecastInputs) -> ForecastResult:
        expected = expected_items(inputs)
        recurring = _without_duplicates(expected, _pattern_items(inputs))
        in_patterns = {t for p in inputs.patterns for t in p.transaction_ids}
        estimate, sigma = _estimate(
            inputs, lambda t: t.label == "normal" and t.id not in in_patterns
        )
        return _result(
            inputs, expected + recurring + _card_items(inputs) + estimate, sigma
        )


class RollingAverageStrategy:
    """The fallback: expected payments plus a weekly average of every other recent
    transaction, with no patterns and no card payments (AC 14, AC 15)."""

    name: ClassVar[str] = "rolling_average"

    def forecast(self, inputs: ForecastInputs) -> ForecastResult:
        estimate, sigma = _estimate(inputs, lambda t: t.label not in NOT_SPENDING)
        return _result(inputs, expected_items(inputs) + estimate, sigma)


register(RecurringPatternStrategy())
register(RollingAverageStrategy())
