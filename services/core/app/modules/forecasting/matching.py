"""Expected payment occurrences, and matching them to real transactions (spec 20).

Pure: no I/O and no clock. The same payments and transactions give the same matches,
whatever order they come in (AC 16).
"""

import bisect
import calendar
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

# A transaction can arrive up to 7 days before or 14 days after the expected date, and
# within 10% of the expected amount (approved by the user on 2026-10-06).
EARLY_DAYS = 7
LATE_DAYS = 14
TOLERANCE_PERCENT = 10

_DAYS = {"weekly": 7, "biweekly": 14}
_MONTHS = {"monthly": 1, "quarterly": 3}


class PaymentLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def created_at(self) -> datetime: ...
    @property
    def amount_cents(self) -> int: ...
    @property
    def currency(self) -> str: ...
    @property
    def date(self) -> date: ...
    @property
    def repeats(self) -> str | None: ...


class TransactionLike(Protocol):
    @property
    def id(self) -> uuid.UUID: ...
    @property
    def date(self) -> date: ...
    @property
    def amount_cents(self) -> int: ...
    @property
    def currency(self) -> str: ...
    @property
    def label(self) -> str: ...


@dataclass(frozen=True)
class Match:
    expected_payment_id: uuid.UUID
    occurrence_date: date
    transaction_id: uuid.UUID


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year, month = start.year + month_index // 12, month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def occurrences(start: date, repeats: str | None) -> Iterator[date]:
    """Every occurrence from `start`, in order; endless unless `repeats` is None.

    Monthly and quarterly ones fall on `start`'s day of the month, or on the month's last
    day when the month is shorter (AC 13).
    """
    if repeats is None:
        yield start
        return
    n = 0
    while True:
        if repeats in _DAYS:
            yield start + timedelta(days=_DAYS[repeats] * n)
        else:
            yield _add_months(start, _MONTHS[repeats] * n)
        n += 1


def occurrences_until(start: date, repeats: str | None, until: date) -> list[date]:
    """The occurrences dated on or before `until`."""
    found = []
    for day in occurrences(start, repeats):
        if day > until:
            break
        found.append(day)
    return found


def _is_candidate(transaction: TransactionLike, payment: PaymentLike) -> bool:
    expected = payment.amount_cents
    actual = transaction.amount_cents
    return (
        transaction.label == "normal"
        and transaction.currency == payment.currency
        and (actual > 0) == (expected > 0)
        and 100 * abs(actual - expected) <= TOLERANCE_PERCENT * abs(expected)
    )


def match(
    payments: Sequence[PaymentLike], transactions: Sequence[TransactionLike]
) -> list[Match]:
    """Pair occurrences with transactions, each at most once (AC 14, AC 15).

    Occurrences go in order of date, then the payment's `created_at`, then its `id`; each
    takes the free candidate closest in amount, then in days, then the earlier, then the
    smaller ID.
    """
    if not transactions:
        return []
    ordered = sorted(transactions, key=lambda t: (t.date, t.id))
    dates = [t.date for t in ordered]
    # No transaction is dated after the newest, so no later occurrence can match.
    last = dates[-1] + timedelta(days=EARLY_DAYS)
    queue = sorted(
        (
            (day, p.created_at, p.id, p)
            for p in payments
            for day in occurrences_until(p.date, p.repeats, last)
        ),
        key=lambda item: item[:3],
    )
    used: set[uuid.UUID] = set()
    found = []
    for day, _, _, payment in queue:
        low = bisect.bisect_left(dates, day - timedelta(days=EARLY_DAYS))
        high = bisect.bisect_right(dates, day + timedelta(days=LATE_DAYS))
        candidates = [
            t
            for t in ordered[low:high]
            if t.id not in used and _is_candidate(t, payment)
        ]
        if not candidates:
            continue
        best = min(
            candidates,
            key=lambda t: (
                abs(t.amount_cents - payment.amount_cents),
                abs((t.date - day).days),
                t.date,
                t.id,
            ),
        )
        used.add(best.id)
        found.append(Match(payment.id, day, best.id))
    return found
