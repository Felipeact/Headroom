"""Running a forecast: the weeks, the inputs' fingerprint, and the strategy fallback.

`CashFlowForecastService` runs the strategy `FORECAST_STRATEGY` selects (AD-078). New
methods are added as strategies in `strategies`, never here.
"""

import dataclasses
import hashlib
import json
import uuid
from collections.abc import Collection, Iterable
from datetime import date, datetime, timedelta
from statistics import median_high, median_low
from zoneinfo import ZoneInfo

import structlog

from app.modules.forecasting.strategies import (
    NOT_SPENDING,
    STRATEGIES,
    WEEKS,
    ForecastInputs,
    ForecastResult,
    InputTransaction,
)

log = structlog.get_logger(__name__)

FALLBACK = "rolling_average"


def business_today(now: datetime, time_zone: str) -> date:
    """`now`'s date in the business's time zone (door 6)."""
    return now.astimezone(ZoneInfo(time_zone)).date()


def week_starts(today: date) -> tuple[date, ...]:
    """The 13 Mondays, the first on or after `today` (AD-082)."""
    first = today + timedelta(days=-today.weekday() % 7)
    return tuple(first + timedelta(weeks=n) for n in range(WEEKS))


def _canonical(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (list, tuple, frozenset, set)):
        items = [_canonical(v) for v in value]
        if isinstance(value, (frozenset, set)):
            return sorted(items, key=str)
        return items
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    return value


def _sorted(rows: list[object]) -> list[object]:
    return sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))


# The weeks of spending the suggested minimum balance looks back on (spec 23, AC 3).
SUGGESTION_WEEKS = 13
SUGGESTION_ROUNDING_CENTS = 10_000


def suggested_minimum(
    transactions: Iterable[InputTransaction],
    cash_account_ids: Collection[uuid.UUID],
    today: date,
) -> int | None:
    """About two weeks of typical spending: 2 × the median weekly money out (AD-088).

    Weeks run Monday to Sunday; only the 13 complete weeks before `today`'s week count,
    and none before the week of the oldest outflow. Money out is every outflow on a
    cash account except transfers. Rounded up to the next $100; None with no complete
    week.
    """
    this_monday = today - timedelta(days=today.weekday())
    outflows = [
        t
        for t in transactions
        if t.amount_cents < 0
        and t.account_id in cash_account_ids
        and t.label not in NOT_SPENDING
    ]
    if not outflows:
        return None
    oldest = min(t.date for t in outflows)
    first = max(
        oldest - timedelta(days=oldest.weekday()),
        this_monday - timedelta(weeks=SUGGESTION_WEEKS),
    )
    weeks = (this_monday - first).days // 7
    if weeks <= 0:
        return None
    totals = [0] * weeks
    for t in outflows:
        if first <= t.date < this_monday:
            totals[(t.date - first).days // 7] -= t.amount_cents
    # 2 × the median, kept in whole cents: the two middle weeks added together.
    doubled = median_low(totals) + median_high(totals)
    return -(-doubled // SUGGESTION_ROUNDING_CENTS) * SUGGESTION_ROUNDING_CENTS


def whole_months(since: date, today: date) -> int:
    """Complete months from `since` to `today`: June 26 to September 26 is 3."""
    months = (today.year - since.year) * 12 + today.month - since.month
    return months - 1 if today.day < since.day else months


def fingerprint(inputs: ForecastInputs, strategy: str) -> str:
    """SHA-256 of the canonical inputs and the strategy name (AD-077).

    Collections are sorted, so the order they were read in never matters, and patterns
    enter by content: a refresh issues new pattern IDs for the same patterns (AD-071).
    """
    document: dict[str, object] = {}
    for field in dataclasses.fields(inputs):
        value = getattr(inputs, field.name)
        if field.name == "patterns":
            value = [{**dataclasses.asdict(p), "id": None} for p in value]
        elif isinstance(value, tuple) and value and dataclasses.is_dataclass(value[0]):
            value = [dataclasses.asdict(v) for v in value]
        canonical = _canonical(value)
        if field.name != "week_starts" and isinstance(canonical, list):
            canonical = _sorted(canonical)
        document[field.name] = canonical
    document["strategy"] = strategy
    text = json.dumps(document, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


class StrategyWeekCountError(Exception):
    """A strategy returned other than 13 weeks."""


class CashFlowForecastService:
    """Runs the selected strategy, and `rolling_average` when it fails (AC 6)."""

    def __init__(self, selected: str) -> None:
        self.selected = selected

    def run(
        self, inputs: ForecastInputs, *, business_id: uuid.UUID
    ) -> tuple[str, ForecastResult]:
        """The strategy that produced the forecast, and the forecast.

        A selected strategy that raises or breaks the 13-week rule is logged as
        `forecast.strategy_failed` and replaced by the fallback. A failing fallback raises.
        """
        try:
            result = STRATEGIES[self.selected].forecast(inputs)
            if len(result.weeks) != WEEKS:
                raise StrategyWeekCountError
            return self.selected, result
        except Exception as exc:  # noqa: BLE001 - any strategy failure falls back
            log.error(
                "forecast.strategy_failed",
                business_id=str(business_id),
                strategy=self.selected,
                error_type=type(exc).__name__,
            )
        return FALLBACK, STRATEGIES[FALLBACK].forecast(inputs)
