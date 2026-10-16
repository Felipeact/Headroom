"""Spec 15: the nightly sync job, driven by a simulated clock.

`run_due` syncs every connection in the database, so these tests run against a database
of their own (`isolated_database`), with the bank tables emptied before each test. A fake
Plaid client stands in for Plaid and records, per access token, when it was asked to sync.
"""

import ast
import dataclasses
import inspect
import threading
import time
import uuid
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from psycopg.errors import LockNotAvailable
from sqlalchemy import select, text, update
from sqlalchemy.exc import OperationalError

from app.db import get_sessionmaker
from app.jobs import nightly
from app.jobs.run_due import RunSummary, run_due
from app.modules.accounts import repository as accounts_repository
from app.modules.bank_sync import repository, service
from app.modules.bank_sync.models import BankConnection, BankTransaction
from app.modules.bank_sync.plaid import PlaidAccount, PlaidError, SyncPage
from app.modules.bank_sync.tokens import encrypt_access_token
from tests.test_transaction_sync import SyncFake, checking, page, snapshot, tx

pytestmark = pytest.mark.usefixtures("isolated_database")

UTC = ZoneInfo("UTC")
TORONTO = "America/Toronto"
VANCOUVER = "America/Vancouver"
ST_JOHNS = "America/St_Johns"
ALL_ZONES = (
    "America/St_Johns",
    "America/Halifax",
    "America/Toronto",
    "America/Winnipeg",
    "America/Regina",
    "America/Edmonton",
    "America/Vancouver",
    "America/Whitehorse",
)
JOB = "nightly_bank_sync"
CREATED_AT = datetime(2026, 10, 5, 12, tzinfo=ZoneInfo("UTC"))
APP = Path(__file__).resolve().parents[1] / "app"


def login_required() -> PlaidError:
    return PlaidError(
        error_type="ITEM_ERROR", error_code="ITEM_LOGIN_REQUIRED", request_id="req-n1"
    )


class NightlyFake(SyncFake):
    """`SyncFake` that answers per access token and records when each token synced.

    `updates[token]` holds the pages a token's next syncs return, in order; with none
    left, a token gets an empty update. `raises[token]` makes every sync of that token
    raise; `fail_times[token]` makes its next N syncs raise `login_required()`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.clock: datetime | None = None
        self.synced: list[tuple[str, datetime | None]] = []
        self.updates: dict[str, list[SyncPage]] = {}
        self.raises: dict[str, Exception] = {}
        self.fail_times: dict[str, int] = {}
        self.hold: threading.Event | None = None
        self._sync_lock = threading.Lock()

    def sync_transactions(self, access_token: str, cursor: str | None) -> SyncPage:
        with self._sync_lock:
            first = not self.synced
            self.synced.append((access_token, self.clock))
        if self.hold is not None and first:
            self.entered.set()
            assert self.hold.wait(10)
        if access_token in self.raises:
            raise self.raises[access_token]
        if self.fail_times.get(access_token, 0) > 0:
            self.fail_times[access_token] -= 1
            raise login_required()
        pages = self.updates.get(access_token)
        if pages:
            return pages.pop(0)
        return page([], cursor=cursor or "")

    def times(self, token: str) -> list[datetime | None]:
        return [at for t, at in self.synced if t == token]


@dataclasses.dataclass(frozen=True)
class Conn:
    business_id: uuid.UUID
    connection_id: uuid.UUID
    token: str
    account: PlaidAccount
    time_zone: str


def new_business(time_zone: str) -> uuid.UUID:
    with get_sessionmaker()() as session:
        business = accounts_repository.insert_business(
            session,
            name=f"Nightly {uuid.uuid4().hex[:6]}",
            province="ON",
            time_zone=time_zone,
        )
        session.commit()
        return business.id


def new_connection(
    time_zone: str,
    *,
    business_id: uuid.UUID | None = None,
    created_at: datetime | None = None,
    synced_on: date | None = None,
) -> Conn:
    """A connection with one checking account and its own access token."""
    bid = business_id or new_business(time_zone)
    token = f"access-sandbox-nightly-{uuid.uuid4().hex}"
    account = checking()
    with get_sessionmaker()() as session:
        connection = repository.insert_connection(
            session,
            business_id=bid,
            plaid_item_id=f"item-{uuid.uuid4().hex}",
            plaid_institution_id=f"ins_{uuid.uuid4().hex[:8]}",
            institution_name="TD Canada Trust",
            access_token_ciphertext=encrypt_access_token(token),
        )
        repository.insert_accounts(
            session,
            [service._account(account, business_id=bid, connection_id=connection.id)],
        )
        # A fixed date before every simulated night, never the real `now()`: the tests'
        # clocks are fixed dates, and a connection is not due on the night it was made.
        connection.created_at = created_at or CREATED_AT
        connection.nightly_synced_on = synced_on
        session.commit()
        return Conn(bid, connection.id, token, account, time_zone)


def state(c: Conn) -> dict[str, Any]:
    with get_sessionmaker()() as session:
        row = session.scalars(
            select(BankConnection).where(BankConnection.id == c.connection_id)
        ).one()
        return {
            "nightly_synced_on": row.nightly_synced_on,
            "nightly_attempts": row.nightly_attempts,
            "next_nightly_attempt_at": row.next_nightly_attempt_at,
            "failed_nights": row.failed_nights,
        }


def set_failed_nights(c: Conn, value: int) -> None:
    with get_sessionmaker()() as session:
        session.execute(
            update(BankConnection)
            .where(BankConnection.id == c.connection_id)
            .values(failed_nights=value)
        )
        session.commit()


def needs_attention(c: Conn) -> bool:
    with get_sessionmaker()() as session:
        return service.needs_attention(
            session, business_id=c.business_id, connection_id=c.connection_id
        )


def local(time_zone: str, *args: int) -> datetime:
    return datetime(*args, tzinfo=ZoneInfo(time_zone))  # type: ignore[misc]


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[misc]


def hourly(start: datetime, end: datetime) -> Iterator[datetime]:
    """Minute 0 of every UTC hour from `start` to `end`, both included."""
    moment = start.astimezone(UTC)
    while moment <= end:
        yield moment
        moment += timedelta(hours=1)


def run(fake: NightlyFake, now: datetime) -> dict[str, int]:
    fake.clock = now
    summary: RunSummary = run_due(now)
    return dict(summary[JOB])


def night_at(moment: datetime, time_zone: str) -> date:
    return (moment.astimezone(ZoneInfo(time_zone)) - timedelta(hours=2)).date()


def local_times(fake: NightlyFake, c: Conn) -> list[datetime]:
    """When each sync of `c` ran, in its business's time zone."""
    return [
        at.astimezone(ZoneInfo(c.time_zone))
        for at in fake.times(c.token)
        if at is not None
    ]


@pytest.fixture(autouse=True)
def _empty_bank_tables() -> None:
    with get_sessionmaker()() as session:
        session.execute(
            text("TRUNCATE bank_transactions, bank_accounts, bank_connections")
        )
        session.commit()


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> NightlyFake:
    plaid = NightlyFake()
    monkeypatch.setattr(nightly, "get_plaid_client", lambda: plaid)
    return plaid


# S1 - every business's banks sync once a night, around 2 AM local time


def test_due_connection_synced_once(fake: NightlyFake) -> None:
    c = new_connection(TORONTO)

    run(fake, utc(2026, 10, 20, 6))

    assert fake.times(c.token) == [utc(2026, 10, 20, 6)]
    assert state(c)["nightly_synced_on"] == date(2026, 10, 20)


def test_not_again_same_night(fake: NightlyFake) -> None:
    c = new_connection(TORONTO)
    run(fake, utc(2026, 10, 20, 6))

    for now in hourly(utc(2026, 10, 20, 7), utc(2026, 10, 21, 5)):
        run(fake, now)

    assert fake.times(c.token) == [utc(2026, 10, 20, 6)]


def test_fall_back_window(fake: NightlyFake) -> None:
    start, end = utc(2026, 10, 25, 0), utc(2026, 11, 7, 23)
    vancouver = new_connection(VANCOUVER, synced_on=night_at(start, VANCOUVER))
    st_johns = new_connection(ST_JOHNS, synced_on=night_at(start, ST_JOHNS))

    for now in hourly(start, end):
        run(fake, now)

    days = [date(2026, 10, 25) + timedelta(days=n) for n in range(14)]
    assert local_times(fake, vancouver) == [
        local(VANCOUVER, d.year, d.month, d.day, 2, 0) for d in days
    ]
    assert local_times(fake, st_johns) == [
        local(ST_JOHNS, d.year, d.month, d.day, 2, 30) for d in days
    ]
    # British Columbia keeps UTC-7 from 2026-11-01 (tzdata 2026.4): 09:00 UTC every night.
    assert [at.hour for at in fake.times(vancouver.token) if at] == [9] * 14


def test_spring_forward_window(fake: NightlyFake) -> None:
    start, end = utc(2027, 3, 7, 0), utc(2027, 3, 20, 23)
    vancouver = new_connection(VANCOUVER, synced_on=night_at(start, VANCOUVER))
    st_johns = new_connection(ST_JOHNS, synced_on=night_at(start, ST_JOHNS))

    for now in hourly(start, end):
        run(fake, now)

    days = [date(2027, 3, 7) + timedelta(days=n) for n in range(14)]
    spring = date(2027, 3, 14)
    assert local_times(fake, vancouver) == [
        local(VANCOUVER, d.year, d.month, d.day, 2, 0) for d in days
    ]
    assert local_times(fake, st_johns) == [
        local(ST_JOHNS, d.year, d.month, d.day, 3 if d == spring else 2, 30)
        for d in days
    ]


def test_every_time_zone(fake: NightlyFake) -> None:
    start, end = utc(2026, 10, 12, 0), utc(2026, 10, 14, 23)
    conns = [new_connection(z, synced_on=night_at(start, z)) for z in ALL_ZONES]

    for now in hourly(start, end):
        run(fake, now)

    for c in conns:
        nights = [night_at(at, c.time_zone) for at in fake.times(c.token) if at]
        assert nights == [date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 14)], (
            c.time_zone
        )


def test_catch_up_later_same_night(fake: NightlyFake) -> None:
    c = new_connection(TORONTO, synced_on=date(2026, 10, 19))

    run(fake, utc(2026, 10, 20, 11))

    assert fake.times(c.token) == [utc(2026, 10, 20, 11)]
    assert state(c)["nightly_synced_on"] == date(2026, 10, 20)


def test_created_tonight_waits(fake: NightlyFake) -> None:
    c = new_connection(TORONTO, created_at=utc(2026, 10, 20, 19))

    for now in hourly(utc(2026, 10, 20, 20), utc(2026, 10, 21, 5)):
        run(fake, now)
    assert fake.times(c.token) == []

    run(fake, utc(2026, 10, 21, 6))
    assert fake.times(c.token) == [utc(2026, 10, 21, 6)]


def test_each_sync_scoped_to_its_business(fake: NightlyFake) -> None:
    toronto = new_connection(TORONTO)
    vancouver = new_connection(VANCOUVER)
    for c in (toronto, vancouver):
        fake.updates[c.token] = [
            page([c.account], added=[tx(f"n-{c.token[-6:]}", c.account)], cursor="n1")
        ]

    # 10:00 UTC is after 02:00 local in both Toronto and Vancouver.
    run(fake, utc(2026, 10, 20, 10))

    with get_sessionmaker()() as session:
        stored = session.scalars(select(BankTransaction)).all()
        by_business = {(r.business_id, r.plaid_transaction_id) for r in stored}
    assert len(stored) == 2
    for c in (toronto, vancouver):
        assert any(
            business == c.business_id and pid.startswith(f"n-{c.token[-6:]}")
            for business, pid in by_business
        )


def test_one_cross_business_read() -> None:
    repo = (APP / "modules/bank_sync/repository.py").read_text(encoding="utf-8")
    tree = ast.parse(repo)
    unscoped = sorted(
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and "select(BankConnection" in ast.get_source_segment(repo, node)  # type: ignore[operator]
        and "BankConnection.business_id ==" not in ast.get_source_segment(repo, node)  # type: ignore[operator]
    )
    assert unscoped == ["connection_for_item", "nightly_candidates"]

    callers = [
        (path.relative_to(APP).as_posix(), line)
        for path in APP.rglob("*.py")
        for line in path.read_text(encoding="utf-8").splitlines()
        if "nightly_candidates(" in line and "def nightly_candidates" not in line
    ]
    assert [path for path, _ in callers] == ["modules/bank_sync/service.py"]
    assert inspect.isfunction(repository.nightly_candidates)


# S2 - overlapping runs never sync the same connection twice


def test_locked_connection_skipped(fake: NightlyFake) -> None:
    c = new_connection(TORONTO)
    holder = get_sessionmaker()()
    try:
        holder.execute(
            select(BankConnection)
            .where(BankConnection.id == c.connection_id)
            .with_for_update()
        ).one()

        started = time.monotonic()
        counts = run(fake, utc(2026, 10, 20, 6))
        assert time.monotonic() - started < 5
        assert fake.times(c.token) == []
        assert counts["skipped_locked"] == 1
        assert state(c)["nightly_synced_on"] is None
    finally:
        holder.commit()
        holder.close()

    run(fake, utc(2026, 10, 20, 7))
    assert fake.times(c.token) == [utc(2026, 10, 20, 7)]


def test_concurrent_runs_sync_once(fake: NightlyFake) -> None:
    a = new_connection(TORONTO)
    b = new_connection(TORONTO)
    now = utc(2026, 10, 20, 6)
    fake.clock = now
    fake.hold = threading.Event()
    summaries: list[dict[str, int]] = []
    errors: list[BaseException] = []

    def go() -> None:
        try:
            summaries.append(dict(run_due(now)[JOB]))
        except BaseException as exc:  # noqa: BLE001 - reported by the assert below
            errors.append(exc)

    first = threading.Thread(target=go)
    first.start()
    assert fake.entered.wait(10)
    second = threading.Thread(target=go)
    second.start()
    second.join(15)
    fake.hold.set()
    first.join(15)

    assert errors == []
    assert len(fake.times(a.token)) == 1
    assert len(fake.times(b.token)) == 1
    assert state(a)["nightly_synced_on"] == date(2026, 10, 20)
    assert state(b)["nightly_synced_on"] == date(2026, 10, 20)
    assert sum(s["synced"] for s in summaries) == 2


def test_second_run_sees_finished_night(fake: NightlyFake) -> None:
    c = new_connection(TORONTO)
    now = utc(2026, 10, 20, 6)
    run(fake, now)

    counts = run(fake, now)

    assert fake.times(c.token) == [now]
    assert counts["due"] == 0


def test_outcome_in_sync_transaction(fake: NightlyFake) -> None:
    c = new_connection(TORONTO)
    fake.updates[c.token] = [
        page([c.account], added=[tx("xmin-1", c.account)], cursor="x1")
    ]
    fake.hold = threading.Event()
    done = threading.Thread(target=run, args=(fake, utc(2026, 10, 20, 6)))
    done.start()
    try:
        assert fake.entered.wait(10)
        with get_sessionmaker()() as other:
            with pytest.raises(OperationalError) as excinfo:
                other.execute(
                    select(BankConnection)
                    .where(BankConnection.id == c.connection_id)
                    .with_for_update(nowait=True)
                )
            assert isinstance(excinfo.value.orig, LockNotAvailable)
    finally:
        fake.hold.set()
        done.join(15)

    with get_sessionmaker()() as session:
        connection_xmin = session.scalar(
            text("SELECT xmin::text FROM bank_connections WHERE id = :id"),
            {"id": c.connection_id},
        )
        transaction_xmin = session.scalar(
            text("SELECT xmin::text FROM bank_transactions WHERE business_id = :b"),
            {"b": c.business_id},
        )
    assert state(c)["nightly_synced_on"] == date(2026, 10, 20)
    assert connection_xmin is not None
    assert connection_xmin == transaction_xmin


# S3 - failed syncs are retried, and repeated failures are flagged


def seeded_failing(fake: NightlyFake) -> Conn:
    """A Toronto connection with one stored transaction and cursor c0, then failing."""
    c = new_connection(TORONTO)
    fake.updates[c.token] = [
        page([c.account], added=[tx("seed", c.account)], cursor="c0")
    ]
    with get_sessionmaker()() as session:
        service.sync_connection(
            session, fake, business_id=c.business_id, connection_id=c.connection_id
        )
    fake.synced.clear()
    fake.raises[c.token] = login_required()
    return c


def test_retry_delays_grow(fake: NightlyFake) -> None:
    c = seeded_failing(fake)
    before = snapshot(c.business_id)

    expected = [
        (local(TORONTO, 2026, 10, 20, 2), 1, local(TORONTO, 2026, 10, 20, 3)),
        (local(TORONTO, 2026, 10, 20, 3), 2, local(TORONTO, 2026, 10, 20, 5)),
        (local(TORONTO, 2026, 10, 20, 5), 3, local(TORONTO, 2026, 10, 20, 9)),
    ]
    for now, attempts, next_at in expected:
        run(fake, now)
        after = state(c)
        assert after["nightly_attempts"] == attempts
        assert after["next_nightly_attempt_at"] == next_at
        assert snapshot(c.business_id) == before


def test_no_attempt_before_next_attempt_time(fake: NightlyFake) -> None:
    c = seeded_failing(fake)

    for now in hourly(
        local(TORONTO, 2026, 10, 20, 2), local(TORONTO, 2026, 10, 20, 23)
    ):
        run(fake, now)

    assert local_times(fake, c) == [
        local(TORONTO, 2026, 10, 20, h) for h in (2, 3, 5, 9)
    ]


def test_fourth_failure_ends_night(fake: NightlyFake) -> None:
    c = seeded_failing(fake)
    for h in (2, 3, 5, 9):
        run(fake, local(TORONTO, 2026, 10, 20, h))

    assert state(c) == {
        "nightly_synced_on": date(2026, 10, 20),
        "nightly_attempts": 0,
        "next_nightly_attempt_at": None,
        "failed_nights": 1,
    }

    for now in hourly(
        local(TORONTO, 2026, 10, 20, 10), local(TORONTO, 2026, 10, 21, 2)
    ):
        run(fake, now)
    assert local_times(fake, c)[4:] == [local(TORONTO, 2026, 10, 21, 2)]


def test_three_failed_nights_need_attention(fake: NightlyFake) -> None:
    c = seeded_failing(fake)
    # Since spec 17 a login error needs attention at once (AD-061); this test is about
    # repeated failures of any other kind.
    fake.raises[c.token] = PlaidError(
        error_type="API_ERROR", error_code="INTERNAL_SERVER_ERROR", request_id="req-n2"
    )
    seen: list[tuple[int, bool]] = []
    for day in (20, 21, 22):
        for now in hourly(
            local(TORONTO, 2026, 10, day, 2), local(TORONTO, 2026, 10, day, 23)
        ):
            run(fake, now)
        seen.append((state(c)["failed_nights"], needs_attention(c)))

    assert seen == [(1, False), (2, False), (3, True)]


@pytest.mark.parametrize(
    "path", ["sync_connection", "nightly", "sync_connection_fails"]
)
def test_success_clears_attention(fake: NightlyFake, path: str) -> None:
    c = new_connection(TORONTO)
    set_failed_nights(c, 3)
    assert needs_attention(c) is True

    if path == "nightly":
        run(fake, utc(2026, 10, 20, 6))
    else:
        if path == "sync_connection_fails":
            fake.raises[c.token] = login_required()
        with get_sessionmaker()() as session:
            try:
                service.sync_connection(
                    session,
                    fake,
                    business_id=c.business_id,
                    connection_id=c.connection_id,
                )
            except PlaidError:
                assert path == "sync_connection_fails"

    if path == "sync_connection_fails":
        assert state(c)["failed_nights"] == 3
        assert needs_attention(c) is True
    else:
        assert state(c)["failed_nights"] == 0
        assert needs_attention(c) is False


def test_success_after_retries_ends_night(fake: NightlyFake) -> None:
    c = new_connection(TORONTO)
    set_failed_nights(c, 2)
    fake.fail_times[c.token] = 2
    for h in (2, 3, 5):
        run(fake, local(TORONTO, 2026, 10, 20, h))

    assert len(fake.times(c.token)) == 3
    assert state(c) == {
        "nightly_synced_on": date(2026, 10, 20),
        "nightly_attempts": 0,
        "next_nightly_attempt_at": None,
        "failed_nights": 0,
    }


def test_one_failure_does_not_stop_others(fake: NightlyFake) -> None:
    p = new_connection(TORONTO)
    r = new_connection(TORONTO)
    s = new_connection(TORONTO)
    fake.raises[p.token] = login_required()
    fake.raises[r.token] = RuntimeError("boom-secret")

    counts = run(fake, utc(2026, 10, 20, 6))

    assert state(p)["nightly_attempts"] == 1
    assert state(r)["nightly_attempts"] == 1
    assert len(fake.times(s.token)) == 1
    assert state(s)["nightly_synced_on"] == date(2026, 10, 20)
    assert counts["synced"] == 1
    assert counts["failed"] == 2
