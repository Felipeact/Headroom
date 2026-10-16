"""Cash gaps, what explains them (spec 24) and how to fix them (spec 25): pure
functions over one forecast.

Amounts are integer cents in our sign: money in positive, money out negative.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from app.modules.alerts.models import AlertItemKind, FixKind

# An outgoing payment explains a gap when it is at least this share of the money going
# out from the week before the gap to its end (AC 4).
CAUSE_PERCENT = 20
# The money that arrives only after a gap: the 7 days after its last day (AC 5).
AFTER_DAYS = 7
# The forecast's weekly averages name no payment, so they never explain a gap.
NOT_NAMED = "estimate"
# A client pays this much earlier, a payment moves this much later (spec 25 AC 2, 3).
SHIFT_DAYS = 7
# Borrowing covers the shortfall rounded up to whole $1,000 (spec 25 AC 4, 6).
BORROW_STEP_CENTS = 100_000


class Week(Protocol):
    @property
    def starts_on(self) -> date: ...
    @property
    def end_balance_cents(self) -> int: ...


class Item(Protocol):
    @property
    def date(self) -> date: ...
    @property
    def amount_cents(self) -> int: ...
    @property
    def currency(self) -> str: ...
    @property
    def source(self) -> str: ...
    @property
    def source_id(self) -> uuid.UUID | None: ...
    @property
    def description(self) -> str | None: ...
    @property
    def counterparty(self) -> str | None: ...
    @property
    def schedule(self) -> str | None: ...


class Span(Protocol):
    @property
    def starts_on(self) -> date: ...
    @property
    def ends_on(self) -> date: ...


@dataclass(frozen=True)
class Gap:
    starts_on: date
    ends_on: date
    lowest_balance_cents: int
    lowest_week_starts_on: date
    shortfall_cents: int


@dataclass(frozen=True)
class Explanation:
    kind: AlertItemKind
    date: date
    amount_cents: int
    currency: str
    description: str | None
    counterparty: str | None
    source: str
    source_id: uuid.UUID | None
    schedule: str | None


@dataclass(frozen=True)
class CreditLine:
    name: str
    currency: str
    available_cents: int | None


@dataclass(frozen=True)
class Fix:
    kind: FixKind
    # The payment moved, in our sign; or the amount borrowed, positive.
    amount_cents: int
    currency: str
    original_date: date | None
    repay_on: date | None
    # The payment's new date, or the day the money is borrowed.
    date: date
    description: str | None
    counterparty: str | None
    available_cents: int | None
    new_lowest_balance_cents: int


def _gap(run: list[Week], minimum_cents: int) -> Gap:
    lowest = min(run, key=lambda w: (w.end_balance_cents, w.starts_on))
    return Gap(
        starts_on=run[0].starts_on,
        ends_on=run[-1].starts_on + timedelta(days=6),
        lowest_balance_cents=lowest.end_balance_cents,
        lowest_week_starts_on=lowest.starts_on,
        shortfall_cents=minimum_cents - lowest.end_balance_cents,
    )


def find_gaps(weeks: Sequence[Week], minimum_cents: int) -> list[Gap]:
    """Each run of consecutive weeks ending below the minimum, earliest first (AC 1, 2)."""
    found: list[Gap] = []
    run: list[Week] = []
    for week in sorted(weeks, key=lambda w: w.starts_on):
        if week.end_balance_cents < minimum_cents:
            run.append(week)
        elif run:
            found.append(_gap(run, minimum_cents))
            run = []
    if run:
        found.append(_gap(run, minimum_cents))
    return found


def _explanation(kind: AlertItemKind, item: Item) -> Explanation:
    return Explanation(
        kind=kind,
        date=item.date,
        amount_cents=item.amount_cents,
        currency=item.currency,
        description=item.description,
        counterparty=item.counterparty,
        source=item.source,
        source_id=item.source_id,
        schedule=item.schedule,
    )


def explain(gap: Gap, items: Iterable[Item]) -> list[Explanation]:
    """The payments that cause `gap`, then the largest one arriving after it (AC 4-6)."""
    items = list(items)
    first = gap.starts_on - timedelta(days=7)
    window = [i for i in items if first <= i.date <= gap.ends_on and i.amount_cents < 0]
    money_out = -sum(i.amount_cents for i in window)
    causes = sorted(
        (
            i
            for i in window
            if i.source != NOT_NAMED
            and -i.amount_cents * 100 >= CAUSE_PERCENT * money_out
        ),
        key=lambda i: (i.date, i.amount_cents),
    )
    last = gap.ends_on + timedelta(days=AFTER_DAYS)
    after = [
        i
        for i in items
        if gap.ends_on < i.date <= last and i.amount_cents > 0 and i.source != NOT_NAMED
    ]
    found = [_explanation("cause", i) for i in causes]
    if after:
        largest = min(after, key=lambda i: (-i.amount_cents, i.date))
        found.append(_explanation("arrives_after", largest))
    return found


def _overlap(a: Span, b: Span) -> bool:
    return a.starts_on <= b.ends_on and b.starts_on <= a.ends_on


def match[A: Span](
    gaps: Sequence[Gap], alerts: Sequence[A]
) -> tuple[list[tuple[Gap, A | None]], list[A]]:
    """Each gap with the alert it continues or None, and the alerts no gap took (AD-096).

    Gaps are taken earliest first, each with the earliest-starting alert it shares a week
    with that no earlier gap took. `alerts` are the open and dismissed ones.
    """
    taken: set[int] = set()
    pairs: list[tuple[Gap, A | None]] = []
    ordered = sorted(range(len(alerts)), key=lambda n: alerts[n].starts_on)
    for gap in sorted(gaps, key=lambda g: g.starts_on):
        found = next(
            (n for n in ordered if n not in taken and _overlap(gap, alerts[n])), None
        )
        if found is not None:
            taken.add(found)
        pairs.append((gap, None if found is None else alerts[found]))
    return pairs, [a for n, a in enumerate(alerts) if n not in taken]


def _lowest_after(
    weeks: Sequence[Week], moves: Iterable[tuple[int, date, date | None]]
) -> int:
    """The lowest week end once each (amount, from, until) counts only in the weeks
    ending on or after `from` and before `until` (None: never stops counting).

    A moved payment is taken out from its original date and put back from its new one.
    """
    moves = list(moves)
    lowest: int | None = None
    for week in weeks:
        sunday = week.starts_on + timedelta(days=6)
        end = week.end_balance_cents + sum(
            amount
            for amount, start, until in moves
            if start <= sunday and (until is None or sunday < until)
        )
        lowest = end if lowest is None else min(lowest, end)
    assert lowest is not None
    return lowest


def _moved(weeks: Sequence[Week], item: Explanation, new_date: date) -> int:
    return _lowest_after(
        weeks,
        [(-item.amount_cents, item.date, None), (item.amount_cents, new_date, None)],
    )


def _shifted(kind: FixKind, item: Explanation, new_date: date, lowest: int) -> Fix:
    return Fix(
        kind=kind,
        amount_cents=item.amount_cents,
        currency=item.currency,
        date=new_date,
        original_date=item.date,
        repay_on=None,
        description=item.description,
        counterparty=item.counterparty,
        available_cents=None,
        new_lowest_balance_cents=lowest,
    )


def fixes(
    gap: Gap,
    explained: Sequence[Explanation],
    weeks: Sequence[Week],
    credit_lines: Sequence[CreditLine],
    *,
    currency: str,
) -> list[Fix]:
    """The fixes for `gap`, in kind order, each with its new lowest balance (spec 25).

    `explained` is the gap's causes and arrives-after item; `weeks` the forecast's 13.
    A fix that doesn't raise the lowest balance is left out (AC 8).
    """
    found: list[Fix] = []
    after = next((e for e in explained if e.kind == "arrives_after"), None)
    if after is not None:
        new_date = after.date - timedelta(days=SHIFT_DAYS)
        found.append(
            _shifted("pay_early", after, new_date, _moved(weeks, after, new_date))
        )
    causes = [e for e in explained if e.kind == "cause"]
    if causes:
        largest = min(causes, key=lambda e: (e.amount_cents, e.date))
        new_date = largest.date + timedelta(days=SHIFT_DAYS)
        found.append(
            _shifted(
                "move_payment", largest, new_date, _moved(weeks, largest, new_date)
            )
        )
    step = BORROW_STEP_CENTS
    borrow = -(-gap.shortfall_cents // step) * step
    lines = [
        line
        for line in credit_lines
        if line.currency == currency
        and line.available_cents is not None
        and line.available_cents >= gap.shortfall_cents
    ]
    after_gap = gap.ends_on + timedelta(days=1)
    if lines:
        line = min(lines, key=lambda c: (-(c.available_cents or 0), c.name))
        available = line.available_cents or 0
        amount = min(borrow, available)
        repay_on = after_gap if after is None else after.date
        found.append(
            Fix(
                kind="draw_credit",
                amount_cents=amount,
                currency=currency,
                date=gap.starts_on,
                original_date=None,
                repay_on=repay_on,
                description=line.name,
                counterparty=None,
                available_cents=available,
                new_lowest_balance_cents=_lowest_after(
                    weeks, [(amount, gap.starts_on, repay_on)]
                ),
            )
        )
    else:
        found.append(
            Fix(
                kind="financing",
                amount_cents=borrow,
                currency=currency,
                date=gap.starts_on,
                original_date=None,
                repay_on=after_gap,
                description=None,
                counterparty=None,
                available_cents=None,
                new_lowest_balance_cents=_lowest_after(
                    weeks, [(borrow, gap.starts_on, after_gap)]
                ),
            )
        )
    return [f for f in found if f.new_lowest_balance_cents > gap.lowest_balance_cents]
