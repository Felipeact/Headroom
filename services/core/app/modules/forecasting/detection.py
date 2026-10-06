"""Recurring payment detection (spec 19): which payments repeat, and when they come next.

Pure functions over one business's transactions; `service` loads them and stores the
result. Amounts are our sign: money in positive, money out negative. The as-of day is the
date of the newest transaction given, so the result never depends on the clock.
"""

import calendar
import re
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median_low

from app.modules.bank_sync.service import TransactionView, is_business_day
from app.modules.forecasting.models import Schedule

MIN_HITS = 3
# Hits over the larger of the expected dates and the band's transactions.
MIN_SHARE = 0.75
# A transaction joins a band while its absolute amount is at most 115% of the smallest.
BAND_PERCENT = 115
RECENT_AMOUNTS = 6
# A pattern reaches full confidence at this many hits.
FULL_CONFIDENCE_HITS = 6

# In order of interval: the shorter one wins a tie (spec 19 AC 5).
SCHEDULES: tuple[Schedule, ...] = (
    "weekly",
    "biweekly",
    "semimonthly",
    "monthly",
    "quarterly",
)
TOLERANCE_DAYS: dict[Schedule, int] = {
    "weekly": 1,
    "biweekly": 3,
    "semimonthly": 3,
    "monthly": 4,
    "quarterly": 7,
}
# Half the interval: a pattern whose next date is further behind the as-of day stopped.
STOPPED_AFTER_DAYS: dict[Schedule, int] = {
    "weekly": 3,
    "biweekly": 7,
    "semimonthly": 7,
    "monthly": 15,
    "quarterly": 45,
}
CADENCE_DAYS: dict[Schedule, int] = {"weekly": 7, "biweekly": 14}


@dataclass(frozen=True)
class DetectedPattern:
    account_id: uuid.UUID
    counterparty: str
    description: str
    schedule: Schedule
    amount_cents: int
    currency: str
    next_date: date
    confidence: int
    # The transactions on an expected date, oldest first.
    transaction_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class _Fit:
    schedule: Schedule
    share: float
    # (expected date, transaction) for every expected date that has one.
    hits: list[tuple[date, TransactionView]]
    # The expected date after the last hit.
    next_expected: date


def _key(t: TransactionView) -> str:
    if t.counterparty:
        return t.counterparty.strip().lower()
    return " ".join(re.sub(r"\d", "", t.description).lower().split())


def _bands(group: list[TransactionView]) -> list[list[TransactionView]]:
    """The group split by amount, each band within 115% of its smallest amount."""
    bands: list[list[TransactionView]] = []
    for t in sorted(group, key=lambda t: (abs(t.amount_cents), t.date, t.id)):
        if bands and abs(t.amount_cents) * 100 <= abs(bands[-1][0].amount_cents) * (
            BAND_PERCENT
        ):
            bands[-1].append(t)
        else:
            bands.append([t])
    return [sorted(b, key=lambda t: (t.date, t.id)) for b in bands]


def _month_index(day: date) -> int:
    return day.year * 12 + day.month - 1


def _on_day(month_index: int, day_of_month: int) -> date:
    year, month = divmod(month_index, 12)
    last = calendar.monthrange(year, month + 1)[1]
    return date(year, month + 1, min(day_of_month, last))


def _cadence(days: list[date], period: int) -> Callable[[int], date]:
    """The k-th date of a fixed cadence through `days`, anchored on the median offset."""
    first, half = days[0], period // 2
    offset = median_low(((d - first).days + half) % period - half for d in days)
    anchor = first + timedelta(days=offset)
    return lambda k: anchor + timedelta(days=period * k)


def _expected(schedule: Schedule, days: list[date]) -> Callable[[int], date] | None:
    """The schedule's k-th expected date for these days, k counting from any origin."""
    if schedule in CADENCE_DAYS:
        return _cadence(days, CADENCE_DAYS[schedule])
    if schedule == "semimonthly":
        # Split at the midpoint of the extremes: the 1st and the 15th, or the 15th and
        # the 30th, each land on their own side (spec 19 AC 4, amended).
        middle = (min(d.day for d in days) + max(d.day for d in days)) / 2
        low = [d.day for d in days if d.day <= middle]
        high = [d.day for d in days if d.day > middle]
        if not low or not high:
            return None
        pair = (median_low(low), median_low(high))
        return lambda k: _on_day(k // 2, pair[k % 2])
    day_of_month = median_low(d.day for d in days)
    if schedule == "monthly":
        return lambda k: _on_day(k, day_of_month)
    phases = Counter(_month_index(d) % 3 for d in days)
    phase = min(phases, key=lambda p: (-phases[p], p))
    return lambda k: _on_day(k * 3 + phase, day_of_month)


def _first_k(schedule: Schedule, start: date) -> int:
    """A k whose expected date falls before `start`."""
    if schedule in CADENCE_DAYS:
        # The cadence is anchored within half a period of the first day.
        return -1
    if schedule == "semimonthly":
        return (_month_index(start) - 1) * 2
    if schedule == "monthly":
        return _month_index(start) - 1
    return _month_index(start) // 3 - 1


def _fit(schedule: Schedule, band: list[TransactionView]) -> _Fit | None:
    days = [t.date for t in band]
    nth = _expected(schedule, days)
    if nth is None:
        return None
    tolerance = timedelta(days=TOLERANCE_DAYS[schedule])
    start, end = days[0] - tolerance, days[-1] + tolerance
    k = _first_k(schedule, start)
    expected: list[tuple[int, date]] = []
    while (d := nth(k)) <= end:
        if d >= start:
            expected.append((k, d))
        k += 1
    used: set[uuid.UUID] = set()
    hits: list[tuple[date, TransactionView]] = []
    last_k = None
    for k, d in expected:
        near = [t for t in band if t.id not in used and abs(t.date - d) <= tolerance]
        if near:
            t = min(near, key=lambda t: (abs((t.date - d).days), t.date, t.id))
            used.add(t.id)
            hits.append((d, t))
            last_k = k
    share = len(hits) / max(len(expected), len(band))
    if len(hits) < MIN_HITS or share < MIN_SHARE or last_k is None:
        return None
    # Three is the least evidence there is, so it must be three in a row with nothing
    # else in the band: 3 of 4 quarters is too easy to hit by chance (AC 4, amended).
    if len(hits) == MIN_HITS and share < 1:
        return None
    return _Fit(schedule, share, hits, nth(last_k + 1))


def _next_business_day(day: date) -> date:
    while not is_business_day(day):
        day += timedelta(days=1)
    return day


def _median_cents(amounts: list[int]) -> int:
    """The median, rounded half to even to whole cents."""
    ordered = sorted(amounts)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    whole, half = divmod(ordered[middle - 1] + ordered[middle], 2)
    return whole + (half and whole % 2)


def _pattern(band: list[TransactionView], as_of: date) -> DetectedPattern | None:
    fits = [f for s in SCHEDULES if (f := _fit(s, band)) is not None]
    if not fits:
        return None
    best = max(fits, key=lambda f: (f.share, -SCHEDULES.index(f.schedule)))
    next_date = _next_business_day(best.next_expected)
    if (as_of - next_date).days > STOPPED_AFTER_DAYS[best.schedule]:
        return None
    hits = sorted((t for _, t in best.hits), key=lambda t: (t.date, t.id))
    latest = hits[-1]
    return DetectedPattern(
        account_id=latest.account_id,
        counterparty=latest.counterparty or latest.description,
        description=latest.description,
        schedule=best.schedule,
        amount_cents=_median_cents([t.amount_cents for t in band[-RECENT_AMOUNTS:]]),
        currency=latest.currency,
        next_date=next_date,
        confidence=round(100 * best.share * min(1, len(hits) / FULL_CONFIDENCE_HITS)),
        transaction_ids=tuple(t.id for t in hits),
    )


def detect(transactions: Iterable[TransactionView]) -> list[DetectedPattern]:
    """The recurring patterns in one business's transactions.

    Only posted transactions labelled `normal` count: card activity and moves between
    the business's own accounts are never spending (spec 16). Ordered by next date,
    then counterparty, then account.
    """
    transactions = list(transactions)
    if not transactions:
        return []
    as_of = max(t.date for t in transactions)
    groups: dict[tuple[uuid.UUID, str, bool, str], list[TransactionView]] = defaultdict(
        list
    )
    for t in transactions:
        if t.label == "normal" and not t.pending and t.amount_cents != 0:
            groups[(t.account_id, t.currency, t.amount_cents > 0, _key(t))].append(t)
    patterns = [
        p
        for group in groups.values()
        for band in _bands(group)
        if (p := _pattern(band, as_of)) is not None
    ]
    return sorted(
        patterns,
        key=lambda p: (p.next_date, p.counterparty, str(p.account_id), p.amount_cents),
    )
