"""Cash gaps and what explains them (spec 24): pure functions over one forecast.

Amounts are integer cents in our sign: money in positive, money out negative.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

from app.modules.alerts.models import AlertItemKind

# An outgoing payment explains a gap when it is at least this share of the money going
# out from the week before the gap to its end (AC 4).
CAUSE_PERCENT = 20
# The money that arrives only after a gap: the 7 days after its last day (AC 5).
AFTER_DAYS = 7
# The forecast's weekly averages name no payment, so they never explain a gap.
NOT_NAMED = "estimate"


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
