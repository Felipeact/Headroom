"""Spec 22: each week's pinned forecast compared with the actual balance (AD-084, AD-085).

Snapshots and transactions are planted straight into their tables, so each test knows
every number. The job reads every business in the shared test database, so each test
first runs it once at the same moment (`settle`); a second run at that moment then acts
only on what the test planted.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select, update

from app.db import get_sessionmaker
from app.log import configure_logging
from app.modules.bank_sync import service as bank_sync_service
from app.modules.bank_sync.models import BankAccount, BankTransaction
from app.modules.forecasting import service
from app.modules.forecasting.models import (
    ForecastAccuracy,
    ForecastPin,
    ForecastSnapshot,
    ForecastWeek,
)
from tests.test_expected_payments_api import Cash, cash_business
from tests.test_recurring_refresh import log_lines

pytestmark = pytest.mark.usefixtures("migrated_database")

TORONTO = ZoneInfo("America/Toronto")
MONDAY = date(2026, 9, 28)
BASE = 1_000_000


def at(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """A Toronto wall-clock time, in UTC as the job receives it."""
    local = datetime(year, month, day, hour, minute, tzinfo=TORONTO)
    return local.astimezone(UTC)


def settle(now: datetime) -> dict[str, int]:
    return service.record_forecast_accuracy(now)


def plant_snapshot(
    business_id: uuid.UUID,
    first_monday: date = MONDAY,
    *,
    computed_at: datetime | None = None,
    base: int = BASE,
) -> uuid.UUID:
    """A snapshot whose week n starts on first_monday + 7(n - 1) and ends at base + n."""
    snapshot = ForecastSnapshot(
        id=uuid.uuid4(),
        business_id=business_id,
        inputs_sha256=uuid.uuid4().hex * 2,
        strategy="recurring_pattern",
        as_of=first_monday - timedelta(days=2),
        currency="CAD",
        opening_balance_cents=base,
        last_computed_at=computed_at or datetime(2026, 9, 26, 10, tzinfo=UTC),
    )
    with get_sessionmaker()() as session:
        session.add(snapshot)
        session.flush()
        session.add_all(
            ForecastWeek(
                snapshot_id=snapshot.id,
                number=n,
                starts_on=first_monday + timedelta(weeks=n - 1),
                end_balance_cents=base + n,
                low_cents=base,
                high_cents=base + 2 * n,
                money_in_cents=0,
                money_out_cents=0,
            )
            for n in range(1, 14)
        )
        session.commit()
        return snapshot.id


def plant_pin(business_id: uuid.UUID, snapshot_id: uuid.UUID) -> None:
    with get_sessionmaker()() as session:
        session.add(
            ForecastPin(
                business_id=business_id, week_start=MONDAY, snapshot_id=snapshot_id
            )
        )
        session.commit()


def add_tx(cash: Cash, account_id: uuid.UUID, cents: int, day: date) -> None:
    with get_sessionmaker()() as session:
        session.add(
            BankTransaction(
                business_id=uuid.UUID(cash.business_id),
                account_id=account_id,
                provider_transaction_id=f"accuracy-{uuid.uuid4().hex}",
                amount_cents=cents,
                currency="CAD",
                date=day,
                pending=False,
                description="Planted",
                counterparty=None,
                category=None,
                category_detailed=None,
            )
        )
        session.commit()


def set_account(account_id: uuid.UUID, **values: Any) -> None:
    with get_sessionmaker()() as session:
        session.execute(
            update(BankAccount).where(BankAccount.id == account_id).values(**values)
        )
        session.commit()


def pins(business_id: uuid.UUID) -> dict[date, uuid.UUID]:
    with get_sessionmaker()() as session:
        return {
            p.week_start: p.snapshot_id
            for p in session.scalars(
                select(ForecastPin).where(ForecastPin.business_id == business_id)
            )
        }


def rows(business_id: uuid.UUID) -> dict[tuple[date, int], ForecastAccuracy]:
    with get_sessionmaker()() as session:
        found = {
            (r.week_start, r.horizon): r
            for r in session.scalars(
                select(ForecastAccuracy).where(
                    ForecastAccuracy.business_id == business_id
                )
            )
        }
        session.expunge_all()
    return found


@pytest.fixture
def cash() -> Iterator[Cash]:
    """Operating 5,000.00 and Reserve 3,000.00 included; the Visa owes 999.99."""
    business = cash_business()
    set_account(business.operating, balance_cents=500_000)
    set_account(business.reserve, balance_cents=300_000)
    set_account(business.visa, balance_cents=99_999)
    yield business


def test_pins_latest_on_monday(cash: Cash) -> None:
    """ACC-11, ACC-16, edge cases: a business-local Monday; no back-dating."""
    bid = uuid.UUID(cash.business_id)
    first = plant_snapshot(bid)

    # 23:30 on Sunday in Toronto is already Monday in UTC: still the week of Sep 21.
    sunday_night = at(2026, 9, 27, 23, 30)
    settle(sunday_night)
    assert pins(bid) == {date(2026, 9, 21): first}

    settle(at(2026, 9, 28, 0, 30))
    assert pins(bid) == {date(2026, 9, 21): first, MONDAY: first}

    second = plant_snapshot(bid, computed_at=datetime(2026, 9, 28, 12, tzinfo=UTC))
    settle(at(2026, 9, 28, 10))
    assert pins(bid)[MONDAY] == first

    # The job was down for two weeks: only the current week is pinned.
    settle(at(2026, 10, 14, 9))
    assert pins(bid) == {
        date(2026, 9, 21): first,
        MONDAY: first,
        date(2026, 10, 12): second,
    }


def test_no_snapshot_no_pin(cash: Cash) -> None:
    """ACC-12."""
    bid = uuid.UUID(cash.business_id)
    settle(at(2026, 9, 28, 1))
    assert pins(bid) == {}


def test_records_from_the_tuesday_after(cash: Cash) -> None:
    """ACC-13, ACC-14: forecast minus the actual worked back to the target Sunday."""
    bid = uuid.UUID(cash.business_id)
    first = plant_snapshot(bid)
    settle(at(2026, 9, 28, 1))
    add_tx(cash, cash.operating, -20_000, date(2026, 10, 3))
    add_tx(cash, cash.operating, 7_000, date(2026, 10, 6))
    add_tx(cash, cash.reserve, -1_000, date(2026, 10, 7))
    add_tx(cash, cash.visa, -5_000, date(2026, 10, 6))

    settle(at(2026, 10, 5, 23, 59))
    assert rows(bid) == {}

    settle(at(2026, 10, 6, 0, 0))
    found = rows(bid)
    assert set(found) == {(MONDAY, 1)}
    row = found[(MONDAY, 1)]
    actual = 500_000 + 300_000 - (7_000 - 1_000)
    assert (row.target_week_start, row.snapshot_id, row.currency) == (
        MONDAY,
        first,
        "CAD",
    )
    assert (row.forecast_cents, row.actual_cents, row.error_cents) == (
        BASE + 1,
        actual,
        BASE + 1 - actual,
    )

    week_4 = date(2026, 10, 19)
    settle(at(2026, 10, 26, 23))
    assert (MONDAY, 4) not in rows(bid)
    settle(at(2026, 10, 27, 1))
    row = rows(bid)[(MONDAY, 4)]
    assert row.target_week_start == week_4
    assert (row.forecast_cents, row.actual_cents) == (BASE + 4, 800_000)
    assert row.error_cents == BASE + 4 - 800_000


def test_target_week_matched_by_monday(cash: Cash) -> None:
    """ACC-13, ACC-15: the pinned week starting on the target Monday, or no row."""
    bid = uuid.UUID(cash.business_id)
    # A stale snapshot: its week 1 is Sep 7, so Sep 28 is its week 4 and its weeks end
    # on Nov 30, before horizon 13's Dec 21.
    stale = plant_snapshot(bid, date(2026, 9, 7))
    settle(at(2026, 9, 28, 1))
    assert pins(bid)[MONDAY] == stale

    settle(at(2026, 12, 29, 1))
    found = rows(bid)
    assert found[(MONDAY, 1)].forecast_cents == BASE + 4
    assert found[(MONDAY, 4)].forecast_cents == BASE + 7
    assert (MONDAY, 13) not in found


def test_runs_twice_same_result(cash: Cash) -> None:
    """ACC-16: a second run, and later balance changes, leave the rows as they are."""
    bid = uuid.UUID(cash.business_id)
    plant_snapshot(bid)
    settle(at(2026, 9, 28, 1))
    now = at(2026, 10, 6, 2)
    settle(now)
    before = rows(bid)
    assert set(before) == {(MONDAY, 1)}

    assert settle(now) == {"pinned": 0, "recorded": 0, "accuracy_failed": 0}
    set_account(cash.operating, balance_cents=1)
    settle(at(2026, 10, 6, 3))
    after = rows(bid)
    assert {k: (r.actual_cents, r.created_at) for k, r in after.items()} == {
        k: (r.actual_cents, r.created_at) for k, r in before.items()
    }


@pytest.mark.parametrize(
    ("change", "actual"),
    [
        # Reserve counts 0, and its later -1,000.00 is still worked back: 0 + 1,000.00.
        ("null_balance", 500_000 + 1_000),
        # Reserve no longer counts at all.
        ("excluded", 500_000),
    ],
)
def test_accounts_at_record_time(cash: Cash, change: str, actual: int) -> None:
    """Edge cases: a null balance counts as 0; accounts included when recorded count."""
    bid = uuid.UUID(cash.business_id)
    plant_snapshot(bid)
    settle(at(2026, 9, 28, 1))
    if change == "null_balance":
        set_account(cash.reserve, balance_cents=None)
    else:
        set_account(cash.reserve, included=False)
    add_tx(cash, cash.reserve, -1_000, date(2026, 10, 7))
    settle(at(2026, 10, 6, 1))
    assert rows(bid)[(MONDAY, 1)].actual_cents == actual


def test_counts_and_log(cash: Cash, capsys: pytest.CaptureFixture[str]) -> None:
    """ACC-18: counts returned and logged, with no amounts."""
    bid = uuid.UUID(cash.business_id)
    now = at(2026, 10, 6, 4)
    settle(now)
    plant_pin(bid, plant_snapshot(bid))
    configure_logging()
    capsys.readouterr()

    assert settle(now) == {"pinned": 1, "recorded": 1, "accuracy_failed": 0}
    (line,) = [
        x
        for x in log_lines(capsys.readouterr().out)
        if x["event"] == "forecast.accuracy_recorded"
    ]
    assert (line["pinned"], line["recorded"], line["accuracy_failed"]) == (1, 1, 0)
    assert not [k for k in line if "cents" in k or "balance" in k]


def test_one_failure_isolated(
    cash: Cash, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """ACC-17: the failing business is logged by ID and type; the others go on."""
    other = cash_business()
    set_account(other.operating, balance_cents=200_000)
    set_account(other.reserve, balance_cents=0)
    broken, fine = uuid.UUID(cash.business_id), uuid.UUID(other.business_id)
    now = at(2026, 10, 6, 5)
    settle(now)
    planted = {bid: plant_snapshot(bid) for bid in (broken, fine)}
    for bid, snapshot in planted.items():
        plant_pin(bid, snapshot)

    real = bank_sync_service.list_connections

    def failing(session: Any, *, business_id: uuid.UUID) -> Any:
        if business_id == broken:
            raise RuntimeError("secret 123456 cents")
        return real(session, business_id=business_id)

    monkeypatch.setattr(bank_sync_service, "list_connections", failing)
    configure_logging()
    capsys.readouterr()
    counts = settle(now)
    out = capsys.readouterr().out

    assert counts == {"pinned": 1, "recorded": 1, "accuracy_failed": 1}
    # The failed business's work rolls back: no pin for Oct 5, no row.
    assert pins(broken) == {MONDAY: planted[broken]}
    assert set(pins(fine)) == {MONDAY, date(2026, 10, 5)}
    assert rows(broken) == {}
    assert rows(fine)[(MONDAY, 1)].actual_cents == 200_000
    (failed,) = [x for x in log_lines(out) if x["event"] == "forecast.accuracy_failed"]
    assert failed["business_id"] == str(broken)
    assert failed["error_type"] == "RuntimeError"
    assert "123456" not in out
