"""Spec 14: transaction sync. A scripted fake Plaid client stands in for Plaid."""

import dataclasses
import inspect
import json
import threading
import time
import uuid
from collections.abc import Iterator, Sequence
from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select

from app import events
from app.db import get_sessionmaker
from app.log import configure_logging
from app.main import app
from app.modules.bank_sync import repository, service
from app.modules.bank_sync.models import BankAccount, BankConnection, BankTransaction
from app.modules.bank_sync.plaid import (
    PlaidAccount,
    PlaidError,
    PlaidTransaction,
    SyncPage,
    get_plaid_client,
)
from app.modules.bank_sync.tokens import encrypt_access_token
from tests.test_bank_connect import FakePlaid, connect, plaid_account
from tests.test_businesses import BAYVIEW, HARBOR, Caller, _owner

pytestmark = pytest.mark.usefixtures("migrated_database")

ACCESS_TOKEN = "access-sandbox-sync-secret"
MUTATION = "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"
# Plaid transaction IDs are unique across every business (door 1), so each test gets its
# own: tests write short names ("t1") and `tid` makes them unique to the test.
_run = {"id": ""}


def tid(name: str) -> str:
    return f"{name}@{_run['id']}"


@pytest.fixture(autouse=True)
def _unique_transaction_ids() -> None:
    _run["id"] = uuid.uuid4().hex[:12]


def checking() -> PlaidAccount:
    return dataclasses.replace(
        plaid_account("Operating", current=8000.0), available=7900.5
    )


def credit_line() -> PlaidAccount:
    return dataclasses.replace(
        plaid_account(
            "Line of credit", type="credit", subtype="line of credit", current=500.0
        ),
        available=19500.0,
    )


def tx(
    transaction_id: str,
    account: PlaidAccount,
    amount: float = 10.0,
    *,
    day: date = date(2026, 9, 30),
    pending: bool = False,
    pending_id: str | None = None,
    name: str = "Coffee",
    merchant: str | None = None,
    counterparties: tuple[str, ...] = (),
    category: str | None = None,
    detailed: str | None = None,
    iso: str | None = "CAD",
    unofficial: str | None = None,
) -> PlaidTransaction:
    return PlaidTransaction(
        transaction_id=tid(transaction_id),
        account_id=account.account_id,
        amount=amount,
        iso_currency_code=iso,
        unofficial_currency_code=unofficial,
        date=day,
        pending=pending,
        pending_transaction_id=None if pending_id is None else tid(pending_id),
        name=name,
        merchant_name=merchant,
        counterparties=counterparties,
        category=category,
        category_detailed=detailed,
    )


def page(
    accounts: Sequence[PlaidAccount],
    *,
    added: Sequence[PlaidTransaction] = (),
    modified: Sequence[PlaidTransaction] = (),
    removed: Sequence[str] = (),
    cursor: str = "c1",
    more: bool = False,
) -> SyncPage:
    return SyncPage(
        added=list(added),
        modified=list(modified),
        removed=[tid(r) for r in removed],
        accounts=list(accounts),
        next_cursor=cursor,
        has_more=more,
    )


def mutation() -> PlaidError:
    return PlaidError(
        error_type="TRANSACTIONS_ERROR", error_code=MUTATION, request_id="req-m"
    )


class SyncFake(FakePlaid):
    """`FakePlaid` whose `/transactions/sync` answers come from `script`, in order.

    With the script empty it answers an empty update that keeps the cursor and reports
    `idle_accounts`. It records every cursor, and can hold its first sync call open.
    """

    def __init__(self) -> None:
        super().__init__()
        self.script: list[SyncPage | PlaidError] = []
        self.cursors: list[str | None] = []
        self.sync_tokens: list[str] = []
        self.idle_accounts: list[PlaidAccount] = []
        self.hold_first: threading.Event | None = None
        self.entered = threading.Event()
        self.keys: dict[str, dict[str, Any]] = {}
        self.key_calls: list[str] = []

    def sync_transactions(self, access_token: str, cursor: str | None) -> SyncPage:
        self.calls.append("sync")
        self.cursors.append(cursor)
        self.sync_tokens.append(access_token)
        if self.hold_first is not None and len(self.cursors) == 1:
            self.entered.set()
            assert self.hold_first.wait(10)
        if not self.script:
            return page(self.idle_accounts, cursor=cursor or "")
        answer = self.script.pop(0)
        if isinstance(answer, PlaidError):
            raise answer
        return answer

    def get_webhook_verification_key(self, key_id: str) -> dict[str, Any]:
        self.key_calls.append(key_id)
        if "key" in self.fail:
            raise self.fail["key"]
        return self.keys[key_id]


@dataclasses.dataclass(frozen=True)
class Connected:
    business_id: uuid.UUID
    connection_id: uuid.UUID
    provider_item_id: str


def make_connection(business_id: str, accounts: Sequence[PlaidAccount]) -> Connected:
    """A stored connection with these accounts and no cursor, as spec 12 leaves it."""
    bid = uuid.UUID(business_id)
    item_id = f"item-{uuid.uuid4().hex}"
    with get_sessionmaker()() as session:
        connection = repository.insert_connection(
            session,
            business_id=bid,
            provider_item_id=item_id,
            provider_institution_id=f"ins_{uuid.uuid4().hex[:8]}",
            institution_name="TD Canada Trust",
            access_token_ciphertext=encrypt_access_token(ACCESS_TOKEN),
        )
        repository.insert_accounts(
            session,
            [
                service._account(a, business_id=bid, connection_id=connection.id)
                for a in accounts
            ],
        )
        session.commit()
        return Connected(bid, connection.id, item_id)


def sync(fake: SyncFake, c: Connected) -> service.SyncResult:
    with get_sessionmaker()() as session:
        return service.sync_connection(
            session, fake, business_id=c.business_id, connection_id=c.connection_id
        )


def rows(business_id: uuid.UUID) -> dict[str, BankTransaction]:
    with get_sessionmaker()() as session:
        found = {
            r.provider_transaction_id.split("@")[0]: r
            for r in session.scalars(
                select(BankTransaction).where(
                    BankTransaction.business_id == business_id
                )
            )
        }
        session.expunge_all()
    return found


def snapshot(business_id: uuid.UUID) -> dict[str, Any]:
    """Every stored value of the business's transactions, accounts and cursors."""

    def values(row: Any) -> dict[str, Any]:
        return {c.key: getattr(row, c.key) for c in sa_inspect(row).mapper.column_attrs}

    with get_sessionmaker()() as session:
        return {
            "transactions": sorted(
                (
                    values(r)
                    for r in session.scalars(
                        select(BankTransaction).where(
                            BankTransaction.business_id == business_id
                        )
                    )
                ),
                key=lambda v: v["provider_transaction_id"],
            ),
            "accounts": sorted(
                (
                    values(r)
                    for r in session.scalars(
                        select(BankAccount).where(
                            BankAccount.business_id == business_id
                        )
                    )
                ),
                key=lambda v: str(v["id"]),
            ),
            "cursors": [
                c.transactions_cursor
                for c in session.scalars(
                    select(BankConnection).where(
                        BankConnection.business_id == business_id
                    )
                )
            ],
        }


def accounts_by_plaid_id(business_id: uuid.UUID) -> dict[str, BankAccount]:
    with get_sessionmaker()() as session:
        found = {
            a.provider_account_id: a
            for a in session.scalars(
                select(BankAccount).where(BankAccount.business_id == business_id)
            )
        }
        session.expunge_all()
    return found


def cursor_of(c: Connected) -> str | None:
    with get_sessionmaker()() as session:
        return session.scalar(
            select(BankConnection.transactions_cursor).where(
                BankConnection.id == c.connection_id
            )
        )


@pytest.fixture
def fake() -> Iterator[SyncFake]:
    plaid = SyncFake()
    app.dependency_overrides[get_plaid_client] = lambda: plaid
    yield plaid
    app.dependency_overrides.pop(get_plaid_client, None)


@pytest.fixture
def owner() -> tuple[Caller, str]:
    return _owner({**HARBOR, "name": f"Sync {uuid.uuid4().hex[:6]}"})


@pytest.fixture
def published() -> Iterator[list[events.Event]]:
    seen: list[events.Event] = []
    events.subscribe("transactions.synced", seen.append)
    yield seen
    events.unsubscribe("transactions.synced", seen.append)


@pytest.fixture
def setup(owner: tuple[Caller, str]) -> tuple[Connected, PlaidAccount, PlaidAccount]:
    chq, loc = checking(), credit_line()
    return make_connection(owner[1], [chq, loc]), chq, loc


Setup = tuple[Connected, PlaidAccount, PlaidAccount]


# S1 - a sync stores every transaction once, signed and normalized


def test_first_sync_all_pages(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx(f"t{i}", chq) for i in (1, 2, 3)], more=True),
        page([chq, loc], added=[tx("t4", chq), tx("t5", loc)], cursor="c2"),
    ]

    sync(fake, c)

    assert fake.cursors == [None, "c1"]
    assert fake.sync_tokens == [ACCESS_TOKEN, ACCESS_TOKEN]
    assert sorted(rows(c.business_id)) == ["t1", "t2", "t3", "t4", "t5"]


@pytest.mark.parametrize(
    ("amount", "cents"),
    [
        (12.34, -1234),
        (-500.00, 50000),
        (0.0, 0),
        (1234.565, -123456),
        (-0.015, 2),
    ],
)
def test_amount_sign(fake: SyncFake, setup: Setup, amount: float, cents: int) -> None:
    c, chq, loc = setup
    fake.script = [page([chq, loc], added=[tx("t1", chq, amount)])]

    sync(fake, c)

    assert rows(c.business_id)["t1"].amount_cents == cents


def test_currency_source(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page(
            [chq, loc],
            added=[
                tx("iso", chq, iso="CAD", unofficial=None),
                tx("unofficial", chq, iso=None, unofficial="BTC"),
            ],
        )
    ]

    sync(fake, c)

    stored = rows(c.business_id)
    assert stored["iso"].currency == "CAD"
    assert stored["unofficial"].currency == "BTC"


def test_no_currency_fails(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    before = snapshot(c.business_id)
    richer = dataclasses.replace(chq, current=99999.0)
    fake.script = [
        page(
            [richer, loc],
            added=[tx("ok", chq), tx("bad", chq, iso=None, unofficial=None)],
        )
    ]

    with pytest.raises(PlaidError) as excinfo:
        sync(fake, c)

    assert excinfo.value.error_type == "INVALID_RESPONSE"
    assert excinfo.value.error_code == "NO_CURRENCY"
    assert rows(c.business_id) == {}
    assert snapshot(c.business_id) == before
    assert cursor_of(c) is None


def test_date_and_pending(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page(
            [chq, loc],
            added=[
                tx("pending", chq, day=date(2026, 9, 30), pending=True),
                tx("posted", chq, day=date(2026, 9, 28), pending=False),
            ],
        )
    ]

    sync(fake, c)

    stored = rows(c.business_id)
    assert stored["pending"].date == date(2026, 9, 30)
    assert type(stored["pending"].date) is date
    assert stored["pending"].pending is True
    assert stored["posted"].pending is False
    assert stored["posted"].date == date(2026, 9, 28)


@pytest.mark.parametrize(
    ("counterparties", "merchant", "counterparty"),
    [
        (("Coastal Supply Co", "Other Co"), "Birch & Co", "Coastal Supply Co"),
        ((), "Birch & Co", "Birch & Co"),
        ((), None, None),
    ],
)
def test_text_fields(
    fake: SyncFake,
    setup: Setup,
    counterparties: tuple[str, ...],
    merchant: str | None,
    counterparty: str | None,
) -> None:
    c, chq, loc = setup
    fake.script = [
        page(
            [chq, loc],
            added=[
                tx(
                    "t1",
                    chq,
                    name="POS 4471 COASTAL",
                    merchant=merchant,
                    counterparties=counterparties,
                    category="RENT_AND_UTILITIES",
                    detailed="RENT_AND_UTILITIES_RENT",
                ),
                tx("t2", chq, name="Unknown", category=None, detailed=None),
            ],
        )
    ]

    sync(fake, c)

    stored = rows(c.business_id)
    assert stored["t1"].description == "POS 4471 COASTAL"
    assert stored["t1"].counterparty == counterparty
    assert stored["t1"].category == "RENT_AND_UTILITIES"
    assert stored["t1"].category_detailed == "RENT_AND_UTILITIES_RENT"
    assert stored["t2"].description == "Unknown"
    assert stored["t2"].category is None
    assert stored["t2"].category_detailed is None


def test_account_and_business(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [page([chq, loc], added=[tx("on-chq", chq), tx("on-loc", loc)])]

    sync(fake, c)

    accounts = accounts_by_plaid_id(c.business_id)
    stored = rows(c.business_id)
    assert stored["on-chq"].account_id == accounts[chq.account_id].id
    assert stored["on-loc"].account_id == accounts[loc.account_id].id
    assert {r.business_id for r in stored.values()} == {c.business_id}


def test_new_account_added(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    savings = plaid_account("New savings", subtype="savings", current=300.0)
    fake.script = [page([chq, loc, savings], added=[tx("t1", savings)])]

    sync(fake, c)

    accounts = accounts_by_plaid_id(c.business_id)
    assert len(accounts) == 3
    new = accounts[savings.account_id]
    assert new.connection_id == c.connection_id
    assert (new.type, new.currency, new.included, new.is_primary) == (
        "savings",
        "CAD",
        False,
        False,
    )
    assert rows(c.business_id)["t1"].account_id == new.id


def test_balances_refreshed(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page(
            [chq, loc],
            more=True,
            added=[tx("t1", chq)],
        ),
        page(
            [
                dataclasses.replace(chq, current=8000.0, available=7900.5),
                dataclasses.replace(loc, current=500.0, available=19500.0),
            ],
            cursor="c2",
        ),
    ]
    with get_sessionmaker()() as session:
        for account in session.scalars(
            select(BankAccount).where(BankAccount.business_id == c.business_id)
        ):
            account.balance_cents = 1
            account.available_cents = 1
        session.commit()

    sync(fake, c)

    accounts = accounts_by_plaid_id(c.business_id)
    assert accounts[chq.account_id].balance_cents == 800000
    assert accounts[chq.account_id].available_cents == 790050
    assert accounts[loc.account_id].type == "line_of_credit"
    assert accounts[loc.account_id].balance_cents == 50000
    assert accounts[loc.account_id].available_cents == 1950000


def test_cursor_stored(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx("t1", chq)], cursor="c1", more=True),
        page([chq, loc], added=[tx("t2", chq)], cursor="c2"),
    ]

    sync(fake, c)
    assert cursor_of(c) == "c2"

    sync(fake, c)
    assert fake.cursors == [None, "c1", "c2"]


def test_second_sync_changes_nothing(
    fake: SyncFake, setup: Setup, published: list[events.Event]
) -> None:
    c, chq, loc = setup
    fake.script = [
        page(
            [chq, loc],
            added=[tx("t1", chq, 12.0), tx("t2", loc, -40.0, pending=True)],
            cursor="c1",
        )
    ]
    fake.idle_accounts = [chq, loc]
    sync(fake, c)
    before = snapshot(c.business_id)
    published.clear()
    time.sleep(0.05)

    result = sync(fake, c)

    assert fake.cursors[-1] == "c1"
    assert not result.changed
    assert snapshot(c.business_id) == before
    assert published == []


def test_added_twice_one_row(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx("t1", chq, 10.0)], cursor="c1"),
        page([chq, loc], added=[tx("t1", chq, 20.0)], cursor="c2"),
    ]

    sync(fake, c)
    sync(fake, c)

    with get_sessionmaker()() as session:
        found = session.scalars(
            select(BankTransaction).where(
                BankTransaction.provider_transaction_id == tid("t1")
            )
        ).all()
    assert len(found) == 1
    assert found[0].amount_cents == -2000


def test_modified_updates_in_place(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx("t1", chq, 10.0, name="Old")], cursor="c1"),
        page(
            [chq, loc],
            modified=[tx("t1", chq, 15.5, day=date(2026, 10, 1), name="New")],
            cursor="c2",
        ),
    ]
    sync(fake, c)
    first_id = rows(c.business_id)["t1"].id

    sync(fake, c)

    row = rows(c.business_id)["t1"]
    assert row.id == first_id
    assert (row.amount_cents, row.date, row.description) == (
        -1550,
        date(2026, 10, 1),
        "New",
    )


# S2 - pending, removed and failed syncs


def test_removed_is_deleted(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx("a", chq), tx("b", chq)], cursor="c1"),
        page([chq, loc], removed=["a"], cursor="c2"),
    ]

    sync(fake, c)
    sync(fake, c)

    assert sorted(rows(c.business_id)) == ["b"]


def test_unknown_removed_ignored(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx("c", chq)], removed=["nope"], cursor="c9")
    ]

    sync(fake, c)

    assert sorted(rows(c.business_id)) == ["c"]
    assert cursor_of(c) == "c9"


@pytest.mark.parametrize("removal_in_same_page", [False, True])
def test_pending_posts_once(
    fake: SyncFake, setup: Setup, removal_in_same_page: bool
) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx("p1", chq, 25.0, pending=True)], cursor="c1"),
        page(
            [chq, loc],
            added=[tx("t1", chq, 27.5, pending=False, pending_id="p1")],
            removed=["p1"] if removal_in_same_page else [],
            cursor="c2",
        ),
    ]

    sync(fake, c)
    assert sorted(rows(c.business_id)) == ["p1"]
    sync(fake, c)

    stored = rows(c.business_id)
    assert sorted(stored) == ["t1"]
    assert stored["t1"].pending is False
    assert stored["t1"].amount_cents == -2750


def test_mutation_restarts(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx("only-first", chq)], cursor="c1", more=True),
        mutation(),
        page([chq, loc], added=[tx("x", chq)], cursor="c1", more=True),
        page([chq, loc], added=[tx("y", chq)], cursor="c2"),
    ]

    sync(fake, c)

    assert fake.cursors == [None, "c1", None, "c1"]
    assert sorted(rows(c.business_id)) == ["x", "y"]
    assert cursor_of(c) == "c2"


@pytest.mark.parametrize("failure", ["mutation_exhausted", "item_login_required"])
def test_failed_sync_rolls_back(fake: SyncFake, setup: Setup, failure: str) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx("keep", chq), tx("gone", chq)], cursor="c0")
    ]
    sync(fake, c)
    before = snapshot(c.business_id)
    fake.cursors.clear()
    changing = page(
        [dataclasses.replace(chq, current=1.0), loc],
        added=[tx("new", chq)],
        modified=[tx("keep", chq, 99.0)],
        removed=["gone"],
        cursor="c1",
        more=True,
    )
    if failure == "mutation_exhausted":
        fake.script = [changing, mutation()] * 3
    else:
        fake.script = [
            changing,
            PlaidError(
                error_type="ITEM_ERROR",
                error_code="ITEM_LOGIN_REQUIRED",
                request_id="req-2",
            ),
        ]

    with pytest.raises(PlaidError) as excinfo:
        sync(fake, c)

    if failure == "mutation_exhausted":
        assert excinfo.value.error_code == MUTATION
        assert fake.cursors.count("c0") == 3
        assert fake.script == []
    else:
        assert excinfo.value.error_code == "ITEM_LOGIN_REQUIRED"
    assert snapshot(c.business_id) == before


def test_concurrent_syncs_serialize(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.hold_first = threading.Event()
    fake.script = [page([chq, loc], added=[tx("a", chq)], cursor="cA")]
    errors: list[BaseException] = []

    def run() -> None:
        try:
            sync(fake, c)
        except BaseException as exc:  # noqa: BLE001 - reported by the assert below
            errors.append(exc)

    first = threading.Thread(target=run)
    first.start()
    assert fake.entered.wait(10)
    second = threading.Thread(target=run)
    second.start()
    time.sleep(1.0)
    # The second sync is waiting on the connection's lock, not talking to Plaid.
    assert fake.cursors == [None]
    fake.hold_first.set()
    first.join(10)
    second.join(10)

    assert errors == []
    assert fake.cursors == [None, "cA"]
    assert sorted(rows(c.business_id)) == ["a"]


# S3 - other modules hear that data changed


def test_event_published(
    fake: SyncFake, setup: Setup, published: list[events.Event]
) -> None:
    c, chq, loc = setup
    fake.script = [
        page([chq, loc], added=[tx("a", chq), tx("b", chq)], cursor="c1"),
        page(
            [chq, loc],
            added=[tx("c", chq), tx("d", loc)],
            modified=[tx("a", chq, 11.0)],
            removed=["b"],
            cursor="c2",
        ),
        page([dataclasses.replace(chq, current=1.0), loc], cursor="c3"),
    ]
    sync(fake, c)
    published.clear()

    sync(fake, c)

    assert published == [
        events.Event(
            name="transactions.synced",
            business_id=c.business_id,
            payload={
                "connection_id": str(c.connection_id),
                "added": 2,
                "modified": 1,
                "removed": 1,
                "balances_changed": False,
                # "d" is an unpaired credit line outflow: `credit_draw` (spec 16).
                "relabeled": 1,
            },
        )
    ]
    published.clear()

    sync(fake, c)

    assert published == [
        events.Event(
            name="transactions.synced",
            business_id=c.business_id,
            payload={
                "connection_id": str(c.connection_id),
                "added": 0,
                "modified": 0,
                "removed": 0,
                "balances_changed": True,
                "relabeled": 0,
            },
        )
    ]


def test_event_after_commit(fake: SyncFake, setup: Setup) -> None:
    c, chq, loc = setup
    fake.script = [page([chq, loc], added=[tx("a", chq), tx("b", loc)])]
    seen: list[int] = []

    def count_committed(event: events.Event) -> None:
        with get_sessionmaker()() as session:
            seen.append(
                len(
                    session.scalars(
                        select(BankTransaction.id).where(
                            BankTransaction.business_id == event.business_id
                        )
                    ).all()
                )
            )

    events.subscribe("transactions.synced", count_committed)
    try:
        sync(fake, c)
    finally:
        events.unsubscribe("transactions.synced", count_committed)

    assert seen == [2]


# S5 - connecting a bank starts the first sync


def test_connect_starts_sync(fake: SyncFake, owner: tuple[Caller, str]) -> None:
    caller, business_id = owner
    chq, loc = checking(), credit_line()
    fake.accounts = lambda: [chq, loc]
    fake.script = [page([chq, loc], added=[tx("first", chq), tx("second", loc)])]

    response = connect(caller, business_id)

    assert response.status_code == 201
    stored = rows(uuid.UUID(business_id))
    assert sorted(stored) == ["first", "second"]
    with get_sessionmaker()() as session:
        cursor = session.scalar(
            select(BankConnection.transactions_cursor).where(
                BankConnection.id == uuid.UUID(response.json()["id"])
            )
        )
    assert cursor == "c1"


def test_connect_sync_failure(
    fake: SyncFake,
    owner: tuple[Caller, str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    caller, business_id = owner
    chq, loc = checking(), credit_line()
    fake.accounts = lambda: [chq, loc]
    fake.script = [
        PlaidError(
            error_type="ITEM_ERROR", error_code="ITEM_LOGIN_REQUIRED", request_id="r-9"
        )
    ]
    configure_logging()
    capsys.readouterr()

    response = connect(caller, business_id)

    assert response.status_code == 201
    assert len(response.json()["accounts"]) == 2
    assert len(accounts_by_plaid_id(uuid.UUID(business_id))) == 2
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    failed = [line for line in lines if line["event"] == "bank_sync.sync_failed"]
    assert len(failed) == 1
    assert failed[0]["connection_id"] == response.json()["id"]
    assert failed[0]["error_code"] == "ITEM_LOGIN_REQUIRED"


# S7 - bank data stays private


def test_no_secrets_logged(
    fake: SyncFake, setup: Setup, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests import webhook_signing

    c, chq, loc = setup
    fake.keys = {webhook_signing.KID: webhook_signing.jwk()}
    fake.script = [
        page(
            [chq, loc],
            added=[
                tx(
                    "t-secret-1",
                    chq,
                    1234.56,
                    name="Invoice 4471 Coastal Supply",
                    merchant="Birch & Co",
                    counterparties=("Birch & Co",),
                )
            ],
            cursor="c1",
        )
    ]
    fake.idle_accounts = [chq, loc]
    configure_logging()
    capsys.readouterr()

    sync(fake, c)
    content = webhook_signing.body(c.provider_item_id)
    headers = webhook_signing.headers(content)
    response = TestClient(app).post(
        "/v1/webhooks/plaid", content=content, headers=headers
    )
    assert response.status_code == 200

    out = capsys.readouterr()
    logs = out.out + out.err
    lines = [json.loads(line) for line in out.out.splitlines()]
    synced = [line for line in lines if line["event"] == "bank_sync.synced"]
    assert synced and {"connection_id", "added", "modified", "removed"} <= set(
        synced[0]
    )
    assert synced[0]["added"] == 1
    leaks = [
        ACCESS_TOKEN,
        headers["Plaid-Verification"],
        content.decode(),
        "Invoice 4471 Coastal Supply",
        "Birch & Co",
        "1234.56",
        "123456",
    ]
    assert [v for v in leaks if v in logs] == []


def test_tenancy(fake: SyncFake) -> None:
    _, business_a = _owner({**HARBOR, "name": f"A {uuid.uuid4().hex[:6]}"})
    _, business_b = _owner({**BAYVIEW, "name": f"B {uuid.uuid4().hex[:6]}"})
    chq_a, chq_b = checking(), checking()
    a = make_connection(business_a, [chq_a])
    b = make_connection(business_b, [chq_b])

    fake.script = [page([chq_a], added=[tx("a1", chq_a), tx("a2", chq_a)])]
    sync(fake, a)
    assert rows(b.business_id) == {}

    fake.script = [page([chq_b], added=[tx("b1", chq_b)])]
    sync(fake, b)

    assert {r.business_id for r in rows(a.business_id).values()} == {a.business_id}
    assert sorted(rows(a.business_id)) == ["a1", "a2"]
    assert {r.business_id for r in rows(b.business_id).values()} == {b.business_id}
    assert sorted(rows(b.business_id)) == ["b1"]


def test_repository_requires_business() -> None:
    functions = [
        (name, fn)
        for name, fn in inspect.getmembers(repository, inspect.isfunction)
        if fn.__module__ == repository.__name__
    ]
    unscoped_connection_queries = []
    for name, fn in functions:
        source = inspect.getsource(fn)
        parameters = inspect.signature(fn).parameters
        scoped = (
            "business_id" in parameters
            and parameters["business_id"].kind is inspect.Parameter.KEYWORD_ONLY
        )
        if "BankTransaction" in source:
            assert scoped, name
        if "BankConnection" in source and "select(" in source and not scoped:
            unscoped_connection_queries.append(name)

    assert any("BankTransaction" in inspect.getsource(fn) for _, fn in functions)
    # The webhook's item lookup, and the nightly job's list of every connection (spec 15
    # AC 8, its C9): each sync after either one is scoped to the connection's business.
    assert unscoped_connection_queries == ["connection_for_item", "nightly_candidates"]
