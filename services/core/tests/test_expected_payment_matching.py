"""Spec 20: matching real transactions to expected payments (AD-074), counted once."""

import itertools
import json
import random
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import events, subscriptions
from app.db import get_sessionmaker
from app.log import configure_logging
from app.modules.bank_sync import service as bank_sync_service
from app.modules.forecasting import matching, repository, service
from app.modules.forecasting.matching import Match
from app.modules.forecasting.models import ExpectedPayment, ExpectedPaymentMatch
from tests.test_expected_payments_api import (
    Cash,
    _clock,  # noqa: F401 - autouse: the routes' clock is fixed at NOON
    cash_business,
    client,
    listed,
    path,
    plant,
    valid_body,
)
from tests.test_transaction_sync import (
    SyncFake,
    _unique_transaction_ids,  # noqa: F401 - autouse: transaction IDs unique per test
    page,
    sync,
    tx,
)

pytestmark = pytest.mark.usefixtures("migrated_database")

T0 = datetime(2026, 10, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _registered() -> None:
    subscriptions.register()


@dataclass(frozen=True)
class P:
    id: uuid.UUID
    created_at: datetime
    amount_cents: int
    currency: str
    date: date
    repeats: str | None


@dataclass(frozen=True)
class T:
    id: uuid.UUID
    date: date
    amount_cents: int
    currency: str = "CAD"
    pending: bool = False
    label: str = "normal"


def pay(
    amount: int,
    day: date,
    repeats: str | None = None,
    *,
    created: datetime = T0,
    currency: str = "CAD",
) -> P:
    return P(uuid.uuid4(), created, amount, currency, day, repeats)


def txn(amount: int, day: date, **kw: Any) -> T:
    return T(uuid.uuid4(), day, amount, **kw)


def ids_until(p: P, until: date) -> list[date]:
    return matching.occurrences_until(p.date, p.repeats, until)


# S2: occurrences and matching, pure


def test_occurrences() -> None:
    """C17."""
    end = date(2027, 6, 30)
    assert ids_until(pay(1, date(2026, 10, 6)), end) == [date(2026, 10, 6)]
    weekly = ids_until(pay(1, date(2026, 10, 6), "weekly"), end)
    assert weekly[:3] == [date(2026, 10, 6), date(2026, 10, 13), date(2026, 10, 20)]
    assert all((b - a).days == 7 for a, b in itertools.pairwise(weekly))
    biweekly = ids_until(pay(1, date(2026, 10, 6), "biweekly"), end)
    assert biweekly[:3] == [date(2026, 10, 6), date(2026, 10, 20), date(2026, 11, 3)]
    assert ids_until(pay(1, date(2027, 1, 31), "monthly"), end)[:4] == [
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
        date(2027, 4, 30),
    ]
    leap = ids_until(pay(1, date(2028, 1, 31), "monthly"), date(2028, 3, 1))
    assert leap[1] == date(2028, 2, 29)
    assert ids_until(pay(1, date(2026, 11, 30), "quarterly"), end) == [
        date(2026, 11, 30),
        date(2027, 2, 28),
        date(2027, 5, 30),
    ]


EXPECTED_DAY = date(2026, 10, 6)
CANDIDATES: list[tuple[T, bool]] = [
    (txn(90_000, EXPECTED_DAY), True),
    (txn(110_000, EXPECTED_DAY), True),
    (txn(89_999, EXPECTED_DAY), False),
    (txn(110_001, EXPECTED_DAY), False),
    (txn(-100_000, EXPECTED_DAY), False),
    (txn(100_000, date(2026, 9, 29)), True),
    (txn(100_000, date(2026, 10, 20)), True),
    (txn(100_000, date(2026, 9, 28)), False),
    (txn(100_000, date(2026, 10, 21)), False),
    (txn(100_000, EXPECTED_DAY, pending=True), True),
    (txn(100_000, EXPECTED_DAY, pending=False), True),
    (txn(100_000, EXPECTED_DAY, label="internal_transfer"), False),
    (txn(100_000, EXPECTED_DAY, label="card_payment"), False),
    (txn(100_000, EXPECTED_DAY, currency="CAD"), True),
    (txn(100_000, EXPECTED_DAY, currency="USD"), False),
]


@pytest.mark.parametrize(("transaction", "matches"), CANDIDATES)
def test_candidate_edges(transaction: T, matches: bool) -> None:
    """C18: one transaction against a one-off of +100000 on 2026-10-06."""
    payment = pay(100_000, EXPECTED_DAY)
    found = matching.match([payment], [transaction])
    assert (found == [Match(payment.id, EXPECTED_DAY, transaction.id)]) is matches
    assert len(found) == int(matches)


def test_candidate_edges_money_out() -> None:
    """C18: a payment of -100000."""
    payment = pay(-100_000, EXPECTED_DAY)
    assert len(matching.match([payment], [txn(-110_000, EXPECTED_DAY)])) == 1
    assert matching.match([payment], [txn(100_000, EXPECTED_DAY)]) == []


def test_assignment_order() -> None:
    """C19."""
    day = date(2026, 10, 6)
    first = pay(100_000, day, created=T0)
    second = pay(100_000, day, created=T0 + timedelta(seconds=1))
    only = txn(100_000, date(2026, 10, 7))
    assert matching.match([second, first], [only]) == [Match(first.id, day, only.id)]

    payment = pay(100_000, day)
    near_amount = txn(100_000, date(2026, 10, 10))
    near_day = txn(104_000, day)
    assert matching.match([payment], [near_day, near_amount]) == [
        Match(payment.id, day, near_amount.id)
    ]

    two_days = txn(100_000, date(2026, 10, 4))
    one_day = txn(100_000, date(2026, 10, 7))
    assert matching.match([payment], [two_days, one_day]) == [
        Match(payment.id, day, one_day.id)
    ]

    low, high = sorted([txn(100_000, day), txn(100_000, day)], key=lambda t: t.id)
    assert matching.match([payment], [high, low]) == [Match(payment.id, day, low.id)]

    both = matching.match(
        [first, second, payment],
        [only, near_amount, near_day, two_days, one_day, low, high],
    )
    used = [m.transaction_id for m in both]
    assert len(used) == len(set(used))


def all_inputs() -> tuple[list[P], list[T]]:
    payments = [
        pay(100_000, date(2026, 10, 6)),
        pay(100_000, date(2026, 10, 6), created=T0 + timedelta(seconds=1)),
        pay(-50_000, date(2026, 9, 1), "weekly"),
        pay(-50_000, date(2026, 8, 31), "monthly"),
        pay(75_000, date(2026, 9, 15), "biweekly"),
    ]
    transactions = [t for t, _ in CANDIDATES] + [
        txn(-50_000, date(2026, 9, 1) + timedelta(days=7 * n)) for n in range(6)
    ]
    transactions += [txn(-49_000, date(2026, 9, 30)), txn(75_500, date(2026, 9, 29))]
    return payments, transactions


def test_order_and_clock_free(monkeypatch: pytest.MonkeyPatch) -> None:
    """C20."""
    payments, transactions = all_inputs()
    expected = sorted(matching.match(payments, transactions), key=repr)
    assert expected
    for n in range(5):
        rng = random.Random(n)
        shuffled_p, shuffled_t = payments[:], transactions[:]
        rng.shuffle(shuffled_p)
        rng.shuffle(shuffled_t)
        assert sorted(matching.match(shuffled_p, shuffled_t), key=repr) == expected

    class Future(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> "Future":
            return cls(2030, 1, 1, tzinfo=tz)

    monkeypatch.setattr(matching, "datetime", Future)
    assert sorted(matching.match(payments, transactions), key=repr) == expected


# The database: constraints


def payment_row(**changes: Any) -> ExpectedPayment:
    values: dict[str, Any] = {
        "business_id": uuid.uuid4(),
        "account_id": uuid.uuid4(),
        "description": "X",
        "amount_cents": 1,
        "currency": "CAD",
        "date": date(2026, 10, 6),
        "repeats": None,
        **changes,
    }
    return ExpectedPayment(**values)


@pytest.mark.parametrize(
    ("column", "value", "constraint"),
    [
        ("amount_cents", 0, "ck_expected_payments_amount_nonzero"),
        ("repeats", "yearly", "ck_expected_payments_repeats"),
    ],
)
def test_payment_constraints(column: str, value: object, constraint: str) -> None:
    """C13."""
    with get_sessionmaker()() as session:
        session.add(payment_row(**{column: value}))
        with pytest.raises(IntegrityError, match=constraint):
            session.commit()


@pytest.mark.parametrize("repeats", [None, "quarterly"])
def test_payment_constraints_accept(repeats: str | None) -> None:
    """C13: null and a listed word are accepted."""
    row = payment_row(repeats=repeats)
    with get_sessionmaker()() as session:
        session.add(row)
        session.commit()
        assert session.get(ExpectedPayment, row.id) is not None


def test_match_constraints() -> None:
    """C14."""
    with get_sessionmaker()() as session:
        a, b = payment_row(), payment_row()
        session.add_all([a, b])
        session.commit()
        a_id, b_id, business_id = a.id, b.id, a.business_id
    shared = uuid.uuid4()

    def add(payment_id: uuid.UUID, day: date, transaction_id: uuid.UUID) -> None:
        with get_sessionmaker()() as session:
            session.add(
                ExpectedPaymentMatch(
                    expected_payment_id=payment_id,
                    occurrence_date=day,
                    business_id=business_id,
                    transaction_id=transaction_id,
                )
            )
            session.commit()

    add(a_id, date(2026, 10, 6), shared)
    with pytest.raises(
        IntegrityError, match="uq_expected_payment_matches_transaction_id"
    ):
        add(b_id, date(2026, 10, 6), shared)
    with pytest.raises(IntegrityError, match="pk_expected_payment_matches"):
        add(a_id, date(2026, 10, 6), uuid.uuid4())

    with get_sessionmaker()() as session:
        session.delete(session.get(ExpectedPayment, a_id))
        session.commit()
        left = session.scalars(
            select(ExpectedPaymentMatch).where(
                ExpectedPaymentMatch.expected_payment_id == a_id
            )
        ).all()
    assert left == []


# S2: stored matches, refreshed by syncs and writes


def matches_of(business_id: str | uuid.UUID) -> set[tuple[uuid.UUID, date, uuid.UUID]]:
    with get_sessionmaker()() as session:
        return {
            (m.expected_payment_id, m.occurrence_date, m.transaction_id)
            for m in repository.matches(
                session, business_id=uuid.UUID(str(business_id))
            )
        }


def transaction_ids(business_id: str) -> dict[str, uuid.UUID]:
    """Stored transaction IDs by their test name (`tx`'s first argument)."""
    with get_sessionmaker()() as session:
        return {
            t.description: t.id
            for t in bank_sync_service.all_transactions(
                session, business_id=uuid.UUID(business_id)
            )
        }


def money_in(name: str, cash: Cash, cents: int, day: date, **kw: Any) -> Any:
    """A Plaid transaction of `cents` coming in (Plaid's sign: money in is negative)."""
    return tx(name, cash.plaid_operating, -cents / 100, day=day, name=name, **kw)


def expected_now(business_id: str) -> set[tuple[uuid.UUID, date, uuid.UUID]]:
    with get_sessionmaker()() as session:
        bid = uuid.UUID(business_id)
        return {
            (m.expected_payment_id, m.occurrence_date, m.transaction_id)
            for m in matching.match(
                repository.expected_payments(session, business_id=bid),
                bank_sync_service.all_transactions(session, business_id=bid),
            )
        }


def test_sync_rematches() -> None:
    """C21."""
    cash = cash_business()
    other = cash_business()
    acme = plant(cash.business_id, "Acme", date(2026, 10, 6), amount_cents=800_000)
    theirs = plant(
        other.business_id, "Theirs", date(2026, 10, 1), matched_on=(date(2026, 10, 1),)
    )
    others_before = matches_of(other.business_id)
    accounts = [cash.plaid_operating]
    fake = SyncFake()

    fake.script = [
        page(
            accounts,
            added=[money_in("Pending", cash, 800_000, date(2026, 10, 7), pending=True)],
        )
    ]
    sync(fake, cash.connection)
    ids = transaction_ids(cash.business_id)
    assert matches_of(cash.business_id) == {(acme, date(2026, 10, 6), ids["Pending"])}

    fake.script = [
        page(
            accounts,
            removed=["Pending"],
            added=[
                money_in(
                    "Posted", cash, 800_000, date(2026, 10, 8), pending_id="Pending"
                )
            ],
            cursor="c2",
        )
    ]
    sync(fake, cash.connection)
    ids = transaction_ids(cash.business_id)
    assert "Pending" not in ids
    assert matches_of(cash.business_id) == {(acme, date(2026, 10, 6), ids["Posted"])}

    fake.script = [page(accounts, removed=["Posted"], cursor="c3")]
    sync(fake, cash.connection)
    assert matches_of(cash.business_id) == set()
    assert [i["id"] for i in listed(cash)] == [str(acme)]
    assert matches_of(other.business_id) == others_before
    assert {m[0] for m in others_before} == {theirs}


def test_write_rematches() -> None:
    """C22."""
    cash = cash_business()
    fake = SyncFake()
    fake.script = [
        page(
            [cash.plaid_operating],
            added=[money_in("Acme paid", cash, 800_000, date(2026, 10, 5))],
        )
    ]
    sync(fake, cash.connection)

    created = client.post(
        path(cash.business_id),
        json=valid_body(amount_cents=800_000, date="2026-10-06"),
        headers=cash.caller.headers,
    )
    assert created.status_code == 201
    payment_id = uuid.UUID(created.json()["id"])
    assert created.json()["next_date"] is None
    assert {m[0] for m in matches_of(cash.business_id)} == {payment_id}
    assert listed(cash) == []

    updated = client.put(
        path(cash.business_id, payment_id),
        json=valid_body(amount_cents=500_000, date="2026-10-06"),
        headers=cash.caller.headers,
    )
    assert updated.status_code == 200
    assert matches_of(cash.business_id) == set()
    assert [i["id"] for i in listed(cash)] == [str(payment_id)]


def synced_with_match() -> Cash:
    cash = cash_business()
    plant(cash.business_id, "Acme", date(2026, 10, 6), amount_cents=800_000)
    fake = SyncFake()
    fake.script = [
        page(
            [cash.plaid_operating],
            added=[money_in("Acme paid", cash, 800_000, date(2026, 10, 7))],
        )
    ]
    sync(fake, cash.connection)
    assert len(matches_of(cash.business_id)) == 1
    return cash


def event(business_id: str | uuid.UUID) -> events.Event:
    return events.Event(
        name="transactions.synced", business_id=uuid.UUID(str(business_id)), payload={}
    )


def test_same_event_twice() -> None:
    """C23."""
    cash = synced_with_match()
    service.match_expected_payments(event(cash.business_id))
    first = matches_of(cash.business_id)
    service.match_expected_payments(event(cash.business_id))
    assert first and matches_of(cash.business_id) == first


def test_concurrent_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """C24: each matcher sleeps before and after its write, so without the lock the
    second one's delete would miss the first's new rows and break the unique index."""
    cash = synced_with_match()
    real_match = matching.match
    real_replace = repository.replace_matches

    def slow_match(*args: Any) -> list[Match]:
        found = real_match(*args)
        time.sleep(0.5)
        return found

    def slow_replace(*args: Any, **kwargs: Any) -> None:
        real_replace(*args, **kwargs)
        time.sleep(0.5)

    monkeypatch.setattr(matching, "match", slow_match)
    monkeypatch.setattr(repository, "replace_matches", slow_replace)

    def race(*jobs: Any) -> list[BaseException]:
        start = threading.Barrier(len(jobs))
        errors: list[BaseException] = []

        def run(job: Any) -> None:
            start.wait()
            try:
                job()
            except BaseException as exc:  # noqa: BLE001 - reported by the caller
                errors.append(exc)

        threads = [threading.Thread(target=run, args=(job,)) for job in jobs]
        for t in threads:
            t.start()
        for t in threads:
            t.join(20)
        return errors

    def rematch() -> None:
        service.match_expected_payments(event(cash.business_id))

    responses: list[Any] = []

    def post() -> None:
        responses.append(
            client.post(
                path(cash.business_id),
                json=valid_body(amount_cents=800_000, date="2026-10-07"),
                headers=cash.caller.headers,
            )
        )

    assert race(rematch, rematch) == []
    assert matches_of(cash.business_id) == expected_now(cash.business_id)
    assert race(rematch, post) == []
    assert [r.status_code for r in responses] == [201]
    final = matches_of(cash.business_id)
    assert final == expected_now(cash.business_id)
    used = [m[2] for m in final]
    assert len(used) == len(set(used))


def log_lines(out: str) -> list[dict[str, Any]]:
    lines = []
    for line in out.splitlines():
        try:
            lines.append(json.loads(line))
        except ValueError:
            continue
    return lines


def test_failure_keeps_matches(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """C26."""
    cash = synced_with_match()
    before = matches_of(cash.business_id)

    def broken(*args: Any) -> list[Match]:
        raise RuntimeError("matcher broke")

    monkeypatch.setattr(matching, "match", broken)
    configure_logging()
    capsys.readouterr()
    fake = SyncFake()
    fake.script = [
        page(
            [cash.plaid_operating],
            added=[money_in("Later", cash, 100, date(2026, 10, 9))],
            cursor="c9",
        )
    ]
    sync(fake, cash.connection)

    assert "Later" in transaction_ids(cash.business_id)
    assert matches_of(cash.business_id) == before
    failed = [
        line
        for line in log_lines(capsys.readouterr().out)
        if line["event"] == "event.handler_failed"
        and line["handler"].endswith("match_expected_payments")
    ]
    assert len(failed) == 1
    assert failed[0]["error_type"] == "RuntimeError"


def test_matched_logged(capsys: pytest.CaptureFixture[str]) -> None:
    """C27."""
    cash = cash_business()
    plant(
        cash.business_id, "Acme secret invoice", date(2026, 10, 6), amount_cents=800_000
    )
    configure_logging()
    capsys.readouterr()
    fake = SyncFake()
    fake.script = [
        page(
            [cash.plaid_operating],
            added=[
                tx(
                    "Hidden",
                    cash.plaid_operating,
                    -8000.0,
                    day=date(2026, 10, 7),
                    name="Hidden payer text",
                    counterparties=("Hidden Counterparty",),
                )
            ],
        )
    ]
    sync(fake, cash.connection)
    sync_out = capsys.readouterr().out
    matched = [
        line
        for line in log_lines(sync_out)
        if line["event"] == "expected_payments.matched"
    ]
    assert len(matched) == 1
    assert matched[0]["business_id"] == cash.business_id
    assert matched[0]["matches"] == 1

    client.post(
        path(cash.business_id),
        json=valid_body(description="Posted secret note", amount_cents=123_456),
        headers=cash.caller.headers,
    )
    out = sync_out + capsys.readouterr().out
    for secret in (
        "Acme secret invoice",
        "Hidden payer text",
        "Hidden Counterparty",
        "Posted secret note",
        "800000",
        "123456",
    ):
        assert secret not in out


# S3: counted once


def coastal_business() -> tuple[Cash, dict[str, uuid.UUID]]:
    cash = cash_business()
    bid = cash.business_id
    ids = {
        "Acme": plant(bid, "Acme", date(2026, 10, 6), amount_cents=800_000),
        "Coastal": plant(
            bid,
            "Coastal",
            date(2026, 11, 12),
            repeats="quarterly",
            amount_cents=-1_450_000,
        ),
        "Overdue": plant(bid, "Overdue", date(2026, 8, 1), amount_cents=100_000),
        "Old": plant(
            bid, "Old", date(2026, 1, 5), repeats="weekly", amount_cents=-1_000
        ),
    }
    return cash, ids


def open_now(business_id: str) -> list[service.OpenOccurrence]:
    with get_sessionmaker()() as session:
        return service.open_occurrences(
            session,
            business_id=uuid.UUID(business_id),
            today=date(2026, 10, 6),
            until=date(2027, 3, 31),
        )


def test_open_occurrences() -> None:
    """C28."""
    cash, ids = coastal_business()
    found = open_now(cash.business_id)

    by_payment: dict[uuid.UUID, list[date]] = {}
    for o in found:
        by_payment.setdefault(o.expected_payment_id, []).append(o.date)
    old = [date(2026, 9, 28) + timedelta(days=7 * n) for n in range(27)]
    assert old[-1] == date(2027, 3, 29)
    assert by_payment == {
        ids["Acme"]: [date(2026, 10, 6)],
        ids["Coastal"]: [date(2026, 11, 12), date(2027, 2, 12)],
        ids["Overdue"]: [date(2026, 8, 1)],
        ids["Old"]: old,
    }
    acme = next(o for o in found if o.expected_payment_id == ids["Acme"])
    with get_sessionmaker()() as session:
        row = session.get(ExpectedPayment, ids["Acme"])
        assert row is not None
        assert (
            acme.account_id,
            acme.description,
            acme.amount_cents,
            acme.currency,
        ) == (
            row.account_id,
            "Acme",
            800_000,
            "CAD",
        )
    assert all(o.date <= date(2027, 3, 31) for o in found)


def test_matched_counted_once() -> None:
    """C29."""
    cash, ids = coastal_business()
    before = open_now(cash.business_id)
    fake = SyncFake()
    fake.script = [
        page(
            [cash.plaid_operating],
            added=[
                money_in("Acme paid", cash, 790_000, date(2026, 10, 9)),
                money_in("Coastal paid", cash, -1_450_000, date(2026, 11, 13)),
            ],
        )
    ]
    sync(fake, cash.connection)
    after = open_now(cash.business_id)

    assert ids["Acme"] not in {o.expected_payment_id for o in after}
    assert str(ids["Acme"]) not in {i["id"] for i in listed(cash)}
    coastal = [o.date for o in after if o.expected_payment_id == ids["Coastal"]]
    assert coastal == [date(2027, 2, 12)]
    assert sum(o.amount_cents for o in after) == (
        sum(o.amount_cents for o in before) - 800_000 + 1_450_000
    )


# S4


def test_subscribed_second() -> None:
    """C32."""
    assert subscriptions.SUBSCRIPTIONS[:2] == (
        ("transactions.synced", service.refresh_recurring_patterns),
        ("transactions.synced", service.match_expected_payments),
    )
    seen: list[events.Event] = []
    events.subscribe("forecast_inputs.changed", seen.append)
    try:
        synced_with_match()
    finally:
        events.unsubscribe("forecast_inputs.changed", seen.append)
    assert seen == []
