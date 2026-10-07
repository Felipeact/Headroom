"""The backtest (spec 22, AD-083): how close each strategy came on the sample data.

For every Monday after a 13-week warm-up, it forecasts from what was known on the
Saturday before. The inputs hold only transactions dated up to that day, with balances
worked back from the reference ones, labels and patterns as they were then, and no
expected payments. It then compares weeks 1, 4 and 13 with the actual balances. Pure:
no database, no clock.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from app.fixtures.harbor_street import REFERENCE_DAY, SampleAccount, SampleBusiness
from app.modules.bank_sync.service import (
    LabelItem,
    TransactionView,
    label_transactions,
)
from app.modules.forecasting import detection, engine, strategies

HORIZONS = (1, 4, 13)
WARM_UP_WEEKS = 13
CASH_TYPES = ("checking", "savings")
# Stable IDs, so two runs print the same thing (ACC-07).
NAMESPACE = uuid.UUID("5f2c4d0e-22a1-4c1b-9b7e-0b4e2d1f2222")


@dataclass(frozen=True)
class HorizonScore:
    origins: int
    # Origins whose actual balance was 0: left out of the percentages (ACC-06).
    zero_actual: int
    mean_percent: float | None
    worst_percent: float | None
    mean_abs_cents: int | None


def _id(key: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, key)


def _accounts(sample: SampleBusiness) -> list[SampleAccount]:
    return [a for bank in sample.banks for a in bank.accounts]


def _cash_keys(sample: SampleBusiness) -> set[str]:
    return {
        a.key
        for a in _accounts(sample)
        if a.type in CASH_TYPES and a.currency == strategies.CASH_CURRENCY
    }


def _after(sample: SampleBusiness, keys: Iterable[str], day: date) -> int:
    keys = set(keys)
    return sum(
        t.amount_cents for t in sample.history if t.account_key in keys and t.date > day
    )


def actual_balance(sample: SampleBusiness, day: date) -> int:
    """The cash balance at the end of `day`: the reference minus what came after."""
    cash = _cash_keys(sample)
    reference = sum(a.balance_cents for a in _accounts(sample) if a.key in cash)
    return reference - _after(sample, cash, day)


def inputs_at(sample: SampleBusiness, today: date) -> strategies.ForecastInputs:
    """What a forecast made on `today` would have known (ACC-03)."""
    accounts = _accounts(sample)
    cash = _cash_keys(sample)
    known = [t for t in sample.history if t.date <= today]
    labels = label_transactions(
        (
            LabelItem(
                id=_id(t.key),
                account_id=_id(t.account_key),
                amount_cents=t.amount_cents,
                currency=t.currency,
                date=t.date,
                category=t.category,
                category_detailed=t.category_detailed,
            )
            for t in known
        ),
        {_id(a.key): a.type for a in accounts},
        today,
    )
    views = [
        TransactionView(
            id=_id(t.key),
            account_id=_id(t.account_key),
            date=t.date,
            amount_cents=t.amount_cents,
            currency=t.currency,
            pending=False,
            description=t.description,
            counterparty=t.counterparty,
            label=labels[_id(t.key)][0],
            linked_transaction_id=labels[_id(t.key)][1],
        )
        for t in known
    ]
    return strategies.ForecastInputs(
        today=today,
        week_starts=engine.week_starts(today),
        cash_accounts=tuple(
            strategies.CashAccount(
                _id(a.key), a.currency, a.balance_cents - _after(sample, [a.key], today)
            )
            for a in accounts
            if a.key in cash
        ),
        # A card's balance is what is owed; a purchase (negative) after `today` added to it.
        card_accounts=tuple(
            strategies.CardAccount(
                _id(a.key), a.name, a.balance_cents + _after(sample, [a.key], today)
            )
            for a in accounts
            if a.type == "credit_card"
        ),
        transactions=tuple(
            strategies.InputTransaction(
                id=v.id,
                account_id=v.account_id,
                date=v.date,
                amount_cents=v.amount_cents,
                currency=v.currency,
                label=v.label,
                linked_transaction_id=v.linked_transaction_id,
            )
            for v in views
        ),
        patterns=tuple(
            strategies.InputPattern(
                # Patterns enter the forecast by content; any stable ID will do.
                id=_id(f"pattern-{n}"),
                account_id=p.account_id,
                amount_cents=p.amount_cents,
                currency=p.currency,
                description=p.description,
                counterparty=p.counterparty,
                schedule=p.schedule,
                next_date=p.next_date,
                transaction_ids=p.transaction_ids,
            )
            for n, p in enumerate(detection.detect(views))
        ),
        # Every sample expected payment is dated after the reference day.
        open_occurrences=(),
        matched_transaction_ids=frozenset(),
    )


def origins(sample: SampleBusiness) -> list[date]:
    """The Mondays from the first transaction + 13 weeks to the reference day."""
    if not sample.history:
        return []
    start = min(t.date for t in sample.history) + timedelta(weeks=WARM_UP_WEEKS)
    monday = start + timedelta(days=-start.weekday() % 7)
    found = []
    while monday <= REFERENCE_DAY:
        found.append(monday)
        monday += timedelta(weeks=1)
    return found


def _due(monday: date, horizon: int) -> date:
    """The Sunday that ends week `horizon` of a forecast made for `monday`."""
    return monday + timedelta(weeks=horizon - 1, days=6)


def origin_pairs(
    sample: SampleBusiness,
    strategy: str,
    monday: date,
    inputs: strategies.ForecastInputs | None = None,
) -> dict[int, tuple[int, int]]:
    """(forecast, actual) end balances for each horizon whose week has ended."""
    inputs = inputs or inputs_at(sample, monday - timedelta(days=2))
    weeks = strategies.STRATEGIES[strategy].forecast(inputs).weeks
    return {
        h: (weeks[h - 1].end_balance_cents, actual_balance(sample, _due(monday, h)))
        for h in HORIZONS
        if _due(monday, h) <= REFERENCE_DAY
    }


def score(pairs: Iterable[tuple[int, int]]) -> HorizonScore:
    """The error of (forecast, actual) pairs: abs(f - a) / abs(a) x 100 (ACC-05)."""
    pairs = list(pairs)
    percents = [abs(f - a) / abs(a) * 100 for f, a in pairs if a != 0]
    cents = [abs(f - a) for f, a in pairs]
    return HorizonScore(
        origins=len(pairs),
        zero_actual=len(pairs) - len(percents),
        mean_percent=sum(percents) / len(percents) if percents else None,
        worst_percent=max(percents) if percents else None,
        mean_abs_cents=strategies.round_div(sum(cents), len(cents)) if cents else None,
    )


def replay(sample: SampleBusiness) -> dict[str, dict[int, HorizonScore]]:
    """Each registered strategy's score at 1, 4 and 13 weeks."""
    found: dict[str, dict[int, list[tuple[int, int]]]] = {
        name: {h: [] for h in HORIZONS} for name in strategies.STRATEGIES
    }
    for monday in origins(sample):
        inputs = inputs_at(sample, monday - timedelta(days=2))
        for name in strategies.STRATEGIES:
            for h, pair in origin_pairs(sample, name, monday, inputs).items():
                found[name][h].append(pair)
    return {
        name: {h: score(pairs) for h, pairs in by_horizon.items()}
        for name, by_horizon in found.items()
    }
