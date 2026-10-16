"""Spec 19: recurring patterns refreshed on every `transactions.synced` (AD-071)."""

import json
import threading
import time
import uuid
from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import events, subscriptions
from app.db import get_sessionmaker
from app.log import configure_logging
from app.modules.bank_sync import service as bank_sync_service
from app.modules.bank_sync.models import BankTransaction
from app.modules.bank_sync.plaid import PlaidAccount, PlaidTransaction
from app.modules.forecasting import detection, repository, service
from app.modules.forecasting.detection import DetectedPattern
from app.modules.forecasting.models import RecurringPattern
from tests.test_businesses import HARBOR, _owner
from tests.test_transaction_sync import (
    Connected,
    SyncFake,
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
    checking,
    make_connection,
    page,
    sync,
    tx,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

RENT_DAYS = [date(2026, m, 15) for m in range(3, 9)]
FIELDS = (
    "account_id",
    "counterparty",
    "description",
    "schedule",
    "amount_cents",
    "currency",
    "next_date",
    "confidence",
    "transaction_ids",
)


@pytest.fixture(autouse=True)
def _registered() -> None:
    subscriptions.register()


def new_business() -> uuid.UUID:
    return uuid.UUID(_owner({**HARBOR, "name": f"Rec {uuid.uuid4().hex[:6]}"})[1])


def rent(account: PlaidAccount, key: str = "rent") -> list[PlaidTransaction]:
    """A monthly rent of $3,800 (Plaid sign: money out positive)."""
    return [
        tx(
            f"{key}{n}",
            account,
            3800.0,
            day=d,
            name="Rent",
            counterparties=("Wharfside Properties",),
        )
        for n, d in enumerate(RENT_DAYS)
    ]


def synced_with_rent(fake: SyncFake) -> tuple[Connected, PlaidAccount]:
    account = checking()
    c = make_connection(str(new_business()), [account])
    fake.script = [page([account], added=rent(account))]
    sync(fake, c)
    return c, account


def rows(business_id: uuid.UUID) -> list[RecurringPattern]:
    with get_sessionmaker()() as session:
        return list(
            session.scalars(
                select(RecurringPattern).where(
                    RecurringPattern.business_id == business_id
                )
            )
        )


def values(
    found: Sequence[RecurringPattern | DetectedPattern],
) -> list[tuple[Any, ...]]:
    return sorted(
        tuple(
            tuple(v) if isinstance(v := getattr(p, f), (list, tuple)) else v
            for f in FIELDS
        )
        for p in found
    )


def detected_now(business_id: uuid.UUID) -> list[DetectedPattern]:
    with get_sessionmaker()() as session:
        return detection.detect(
            bank_sync_service.all_transactions(session, business_id=business_id)
        )


def plant(business_id: uuid.UUID, counterparty: str = "Ghost Ltd") -> uuid.UUID:
    pattern = RecurringPattern(
        business_id=business_id,
        account_id=uuid.uuid4(),
        counterparty=counterparty,
        description=counterparty,
        schedule="monthly",
        amount_cents=-1_000,
        currency="CAD",
        next_date=date(2026, 10, 1),
        confidence=50,
        transaction_ids=[uuid.uuid4()],
    )
    with get_sessionmaker()() as session:
        session.add(pattern)
        session.commit()
        return pattern.id


def event(business_id: uuid.UUID) -> events.Event:
    return events.Event(name="transactions.synced", business_id=business_id, payload={})


def log_lines(out: str) -> list[dict[str, Any]]:
    lines = []
    for line in out.splitlines():
        try:
            lines.append(json.loads(line))
        except ValueError:
            continue
    return lines


def test_sync_replaces_patterns() -> None:
    """C19."""
    fake = SyncFake()
    account = checking()
    business_id = new_business()
    other = new_business()
    ghost = plant(business_id)
    others_row = plant(other, "Other Co")
    c = make_connection(str(business_id), [account])
    fake.script = [page([account], added=rent(account))]
    sync(fake, c)

    stored = rows(business_id)
    assert len(stored) == 1
    assert ghost not in {r.id for r in stored}
    assert values(stored) == values(detected_now(business_id))
    assert [r.id for r in rows(other)] == [others_row]


def test_same_event_twice() -> None:
    """C20."""
    c, _ = synced_with_rent(SyncFake())
    service.refresh_recurring_patterns(event(c.business_id))
    first = values(rows(c.business_id))
    service.refresh_recurring_patterns(event(c.business_id))
    assert first and values(rows(c.business_id)) == first


def test_concurrent_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    """C21: the second refresh waits for the first; one set remains.

    Each refresh sleeps after its write and before its commit, so without the lock the
    second one's delete would wait on the first's rows, miss its new ones, and insert a
    second set. A delay before the write alone lets the first commit too early.
    """
    c, _ = synced_with_rent(SyncFake())
    expected = len(detected_now(c.business_id))
    real_detect = detection.detect
    real_replace = repository.replace_patterns

    def slow_detect(transactions: Any) -> list[DetectedPattern]:
        found = real_detect(transactions)
        time.sleep(0.5)
        return found

    def slow_replace(*args: Any, **kwargs: Any) -> None:
        real_replace(*args, **kwargs)
        time.sleep(0.5)

    monkeypatch.setattr(detection, "detect", slow_detect)
    monkeypatch.setattr(repository, "replace_patterns", slow_replace)
    start = threading.Barrier(2)
    errors: list[BaseException] = []

    def run() -> None:
        start.wait()
        try:
            service.refresh_recurring_patterns(event(c.business_id))
        except BaseException as exc:  # noqa: BLE001 - reported by the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert errors == []
    stored = rows(c.business_id)
    assert len(stored) == expected
    keys = [(r.account_id, r.counterparty, r.schedule) for r in stored]
    assert len(set(keys)) == len(keys)


def test_no_transactions_no_patterns() -> None:
    """C22."""
    fake = SyncFake()
    c, account = synced_with_rent(fake)
    assert len(rows(c.business_id)) == 1
    fake.script = [
        page(
            [account],
            removed=[f"rent{n}" for n in range(len(RENT_DAYS))],
            cursor="c2",
        )
    ]
    sync(fake, c)
    assert rows(c.business_id) == []


def test_failure_keeps_patterns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C23."""
    fake = SyncFake()
    c, account = synced_with_rent(fake)
    before = {r.id for r in rows(c.business_id)}
    assert len(before) == 1

    def broken(transactions: Any) -> list[DetectedPattern]:
        raise RuntimeError("detector broke")

    monkeypatch.setattr(detection, "detect", broken)
    configure_logging()
    capsys.readouterr()
    fake.script = [
        page(
            [account],
            added=[tx("late", account, 12.0, day=date(2026, 9, 1))],
            cursor="c2",
        )
    ]
    sync(fake, c)

    with get_sessionmaker()() as session:
        count = session.scalar(
            select(func.count())
            .select_from(BankTransaction)
            .where(BankTransaction.business_id == c.business_id)
        )
    assert count == len(RENT_DAYS) + 1
    assert {r.id for r in rows(c.business_id)} == before
    failed = [
        line
        for line in log_lines(capsys.readouterr().out)
        if line["event"] == "event.handler_failed"
    ]
    assert len(failed) == 1
    assert failed[0]["handler"].endswith("refresh_recurring_patterns")
    assert failed[0]["error_type"] == "RuntimeError"


def test_refresh_logged(capsys: pytest.CaptureFixture[str]) -> None:
    """C24."""
    c, _ = synced_with_rent(SyncFake())
    configure_logging()
    capsys.readouterr()
    service.refresh_recurring_patterns(event(c.business_id))
    out = capsys.readouterr().out

    refreshed = [
        line
        for line in log_lines(out)
        if line["event"] == "recurring_patterns.refreshed"
    ]
    assert len(refreshed) == 1
    assert refreshed[0]["business_id"] == str(c.business_id)
    assert refreshed[0]["patterns"] == 1
    for secret in ("Wharfside", "Rent", "380000"):
        assert secret not in out


def test_subscribed_first() -> None:
    """C25."""
    assert subscriptions.SUBSCRIPTIONS[0] == (
        "transactions.synced",
        service.refresh_recurring_patterns,
    )


@pytest.mark.parametrize(
    ("column", "value", "constraint"),
    [
        ("schedule", "yearly", "ck_recurring_patterns_schedule"),
        ("confidence", 101, "ck_recurring_patterns_confidence"),
        ("amount_cents", 0, "ck_recurring_patterns_amount_nonzero"),
    ],
)
def test_constraints_refuse(column: str, value: object, constraint: str) -> None:
    """C26."""
    pattern = RecurringPattern(
        business_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        counterparty="X",
        description="X",
        schedule="monthly",
        amount_cents=-1,
        currency="CAD",
        next_date=date(2026, 10, 1),
        confidence=50,
        transaction_ids=[],
    )
    setattr(pattern, column, value)
    with get_sessionmaker()() as session:
        session.add(pattern)
        with pytest.raises(IntegrityError, match=constraint):
            session.commit()


@pytest.mark.parametrize("confidence", [0, 100])
def test_constraints_refuse_edges_accepted(confidence: int) -> None:
    """C26: the confidence bounds are allowed."""
    business_id = uuid.uuid4()
    with get_sessionmaker()() as session:
        session.add(
            RecurringPattern(
                business_id=business_id,
                account_id=uuid.uuid4(),
                counterparty="X",
                description="X",
                schedule="weekly",
                amount_cents=1,
                currency="CAD",
                next_date=date(2026, 10, 1),
                confidence=confidence,
                transaction_ids=[],
            )
        )
        session.commit()
    assert [r.confidence for r in rows(business_id)] == [confidence]
