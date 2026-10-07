"""Running a forecast: the weeks, the inputs' fingerprint, and the strategy fallback.

`CashFlowForecastService` runs the strategy `FORECAST_STRATEGY` selects (AD-078). New
methods are added as strategies in `strategies`, never here.
"""

import dataclasses
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog

from app.modules.forecasting.strategies import (
    STRATEGIES,
    WEEKS,
    ForecastInputs,
    ForecastResult,
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
