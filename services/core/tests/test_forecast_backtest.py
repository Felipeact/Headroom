"""Spec 22: the backtest replays Harbor Street as it was known on each past day (AD-083).

Pure: no database. Expected values are rebuilt here from the sample and the spec's
rules, never read back from the backtest.
"""

import dataclasses
from datetime import date, timedelta

import pytest

from app.fixtures import harbor_street
from app.fixtures.harbor_street import REFERENCE_DAY, SampleBusiness
from app.modules.forecasting import backtest, strategies

CASH = ("operating", "reserve")


@pytest.fixture(scope="module")
def sample() -> SampleBusiness:
    return harbor_street.generate(0)


def later(sample: SampleBusiness, keys: tuple[str, ...], day: date) -> int:
    return sum(
        t.amount_cents for t in sample.history if t.account_key in keys and t.date > day
    )


def test_inputs_known_then(sample: SampleBusiness) -> None:
    """ACC-03: only what was known on the origin's today."""
    today = date(2026, 6, 13)
    inputs = backtest.inputs_at(sample, today)

    assert inputs.today == today
    assert inputs.week_starts[0] == date(2026, 6, 15)
    known = [t for t in sample.history if t.date <= today]
    assert len(inputs.transactions) == len(known)
    assert max(t.date for t in inputs.transactions) <= today

    balances = sorted(a.balance_cents or 0 for a in inputs.cash_accounts)
    assert balances == sorted(
        [
            harbor_street.OPERATING.balance_cents
            - later(sample, ("operating",), today),
            harbor_street.RESERVE.balance_cents - later(sample, ("reserve",), today),
        ]
    )
    assert {a.currency for a in inputs.cash_accounts} == {"CAD"}
    (card,) = inputs.card_accounts
    assert card.balance_cents == harbor_street.CARD_OWED_CENTS + later(
        sample, ("visa",), today
    )

    known_ids = {t.id for t in inputs.transactions}
    assert inputs.patterns
    for pattern in inputs.patterns:
        assert set(pattern.transaction_ids) <= known_ids
    payroll = [p for p in inputs.patterns if p.counterparty == "Payroll"]
    assert [(p.schedule, p.amount_cents) for p in payroll] == [
        ("biweekly", harbor_street.PAYROLL_CENTS)
    ]
    assert inputs.open_occurrences == ()


def test_labels_as_of_today(sample: SampleBusiness) -> None:
    """ACC-03: a transfer between the two cash accounts is never income or spending."""
    inputs = backtest.inputs_at(sample, date(2026, 6, 13))
    labels = {t.label for t in inputs.transactions}
    assert "internal_transfer" in labels
    assert "card_payment" in labels
    transfer = next(t for t in inputs.transactions if t.label == "internal_transfer")
    assert transfer.linked_transaction_id is not None


def test_actual_balance(sample: SampleBusiness) -> None:
    """ACC-04: the reference cash minus cash transactions after the Sunday."""
    reference = (
        harbor_street.OPERATING.balance_cents + harbor_street.RESERVE.balance_cents
    )
    assert backtest.actual_balance(sample, REFERENCE_DAY) == reference == 4_230_000
    sunday = date(2026, 6, 21)
    assert backtest.actual_balance(sample, sunday) == reference - later(
        sample, CASH, sunday
    )


def test_score() -> None:
    """ACC-05, ACC-06: abs(forecast - actual) / abs(actual) x 100; zero actuals apart."""
    score = backtest.score([(110, 100), (90, 100), (-50, -40), (50, 0)])
    assert score.origins == 4
    assert score.zero_actual == 1
    assert score.mean_percent == pytest.approx((10 + 10 + 25) / 3)
    assert score.worst_percent == pytest.approx(25.0)
    # Cents: 10, 10, 10, 50 -> mean 20.
    assert score.mean_abs_cents == 20


def test_score_empty() -> None:
    """Edge case: no origins is a score of nothing, not an error."""
    score = backtest.score([])
    assert (score.origins, score.zero_actual) == (0, 0)
    assert score.mean_percent is None
    assert score.worst_percent is None
    assert score.mean_abs_cents is None


def expected_origins(sample: SampleBusiness, horizon: int) -> int:
    """The spec's rule, counted here: Mondays from the first transaction + 13 weeks
    whose horizon week ends on or before the reference day."""
    start = min(t.date for t in sample.history) + timedelta(weeks=13)
    monday = start + timedelta(days=-start.weekday() % 7)
    count = 0
    while monday <= REFERENCE_DAY:
        if monday + timedelta(weeks=horizon - 1, days=6) <= REFERENCE_DAY:
            count += 1
        monday += timedelta(weeks=1)
    return count


def test_replay(sample: SampleBusiness) -> None:
    """ACC-01, ACC-07: every strategy at 1, 4 and 13 weeks; the same twice."""
    first = backtest.replay(sample)
    assert set(first) == set(strategies.STRATEGIES)
    for by_horizon in first.values():
        assert set(by_horizon) == {1, 4, 13}
        for horizon, score in by_horizon.items():
            assert score.origins == expected_origins(sample, horizon)
            assert score.mean_percent is not None
    assert expected_origins(sample, 1) == 64
    assert backtest.replay(sample) == first


def test_replay_matches_one_origin(sample: SampleBusiness) -> None:
    """ACC-05 end to end: one origin's error is the strategy's week end vs the actual."""
    monday = date(2026, 6, 15)
    inputs = backtest.inputs_at(sample, monday - timedelta(days=2))
    result = strategies.STRATEGIES["recurring_pattern"].forecast(inputs)
    pairs = backtest.origin_pairs(sample, "recurring_pattern", monday)
    sunday = monday + timedelta(weeks=3, days=6)
    assert pairs[4] == (
        result.weeks[3].end_balance_cents,
        backtest.actual_balance(sample, sunday),
    )


def test_short_history(sample: SampleBusiness) -> None:
    """Edge case: a history shorter than the 13-week warm-up gives 0 origins."""
    short = dataclasses.replace(
        sample,
        history=tuple(
            t for t in sample.history if t.date > REFERENCE_DAY - timedelta(weeks=8)
        ),
    )
    for by_horizon in backtest.replay(short).values():
        assert all(s.origins == 0 for s in by_horizon.values())
