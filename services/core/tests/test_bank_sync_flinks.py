"""Spec 17a S3: Flinks connections sync like Plaid ones. Fakes stand in for both.

Runs against a database of its own, like spec 15's nightly tests, because `run_due`
syncs every connection in the database.
"""

import dataclasses
import uuid
from collections.abc import Iterator
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app import events
from app.db import get_sessionmaker
from app.jobs import nightly
from app.log import configure_logging
from app.main import app
from app.modules.bank_sync import service
from app.modules.bank_sync.flinks import SYNC_POLLS, FlinksAccount, FlinksError
from app.modules.bank_sync.models import BankAccount, BankConnection, BankTransaction
from tests.flinks_support import (
    FakeFlinks,
    flinks_account,
    flinks_tx,
    login_error,
)
from tests.test_bank_connect import FakePlaid
from tests.test_businesses import HARBOR, Caller, _owner
from tests.test_nightly_sync import CREATED_AT, TORONTO, NightlyFake, new_business, run

pytestmark = pytest.mark.usefixtures("isolated_database")

client = TestClient(app)
NOW = datetime.fromisoformat("2026-10-16T12:00:00+00:00")


@dataclasses.dataclass(frozen=True)
class FConn:
    business_id: uuid.UUID
    connection_id: uuid.UUID
    login_id: str


@pytest.fixture(autouse=True)
def _empty_bank_tables() -> None:
    with get_sessionmaker()() as session:
        session.execute(
            text("TRUNCATE bank_transactions, bank_accounts, bank_connections")
        )
        session.commit()


@pytest.fixture
def fake() -> FakeFlinks:
    return FakeFlinks()


@pytest.fixture
def published() -> Iterator[list[events.Event]]:
    seen: list[events.Event] = []
    events.subscribe("transactions.synced", seen.append)
    yield seen
    events.unsubscribe("transactions.synced", seen.append)


def connect(fake: FakeFlinks, *accounts: FlinksAccount) -> FConn:
    """A stored Flinks connection, made before every simulated night."""
    if accounts:
        fake.accounts_list = list(accounts)
    business_id = new_business(TORONTO)
    login_id = str(uuid.uuid4())
    with get_sessionmaker()() as session:
        view = service.connect_flinks_bank(
            session,
            fake,
            business_id=business_id,
            user_id=uuid.uuid4(),
            login_id=login_id,
        )
        session.execute(
            text("UPDATE bank_connections SET created_at = :at WHERE id = :id"),
            {"at": CREATED_AT, "id": view.id},
        )
        session.commit()
    fake.accounts_calls.clear()
    return FConn(business_id, view.id, login_id)


def sync(fake: FakeFlinks, c: FConn, now: datetime = NOW) -> service.SyncResult:
    with get_sessionmaker()() as session:
        return service.sync_connection(
            session,
            FakePlaid(),
            business_id=c.business_id,
            connection_id=c.connection_id,
            now=now,
            flinks=fake,
        )


def connection(c: FConn) -> BankConnection:
    with get_sessionmaker()() as session:
        row = session.scalars(
            select(BankConnection).where(BankConnection.id == c.connection_id)
        ).one()
        session.expunge_all()
    return row


def transactions(c: FConn) -> dict[str, BankTransaction]:
    with get_sessionmaker()() as session:
        found = {
            t.provider_transaction_id: t
            for t in session.scalars(
                select(BankTransaction).where(
                    BankTransaction.business_id == c.business_id
                )
            )
        }
        session.expunge_all()
    return found


def accounts(c: FConn) -> dict[str, BankAccount]:
    with get_sessionmaker()() as session:
        found = {
            a.provider_account_id: a
            for a in session.scalars(
                select(BankAccount).where(BankAccount.business_id == c.business_id)
            )
        }
        session.expunge_all()
    return found


def test_first_sync_days365_then_days90(fake: FakeFlinks) -> None:
    """C22."""
    c = connect(fake)

    sync(fake, c)
    sync(fake, c)

    assert [(a.days, a.with_transactions, a.polls) for a in fake.accounts_calls] == [
        ("Days365", True, SYNC_POLLS),
        ("Days90", True, SYNC_POLLS),
    ]
    assert {a.login_id for a in fake.accounts_calls} == {c.login_id}


def test_transaction_values_and_sign(fake: FakeFlinks) -> None:
    """C23."""
    account = flinks_account()
    c = connect(fake, account)
    fake.transactions = [
        flinks_tx(account, credit=12.345, transaction_id="in", description="DEPOSIT"),
        flinks_tx(
            account,
            debit=50.10,
            transaction_id="out",
            description="HYDRO",
            day=date(2026, 9, 30),
        ),
    ]

    sync(fake, c)

    stored = transactions(c)
    assert (stored["in"].amount_cents, stored["out"].amount_cents) == (1234, -5010)
    assert (stored["in"].pending, stored["out"].pending) == (False, False)
    assert (stored["in"].description, stored["out"].description) == ("DEPOSIT", "HYDRO")
    assert (stored["in"].date, stored["out"].date) == (
        date(2026, 10, 1),
        date(2026, 9, 30),
    )
    assert stored["in"].currency == "CAD"


def test_resync_is_idempotent_and_modifies(fake: FakeFlinks) -> None:
    """C24."""
    account = flinks_account()
    c = connect(fake, account)
    fake.transactions = [
        flinks_tx(account, debit=10.0, transaction_id="a"),
        flinks_tx(account, debit=20.0, transaction_id="b"),
    ]

    first = sync(fake, c)
    again = sync(fake, c)
    fake.transactions = [
        flinks_tx(account, debit=10.0, transaction_id="a"),
        flinks_tx(account, debit=25.0, transaction_id="b"),
    ]
    changed = sync(fake, c)

    assert (first.added, first.modified, first.removed) == (2, 0, 0)
    assert (again.added, again.modified, again.removed) == (0, 0, 0)
    assert (changed.added, changed.modified, changed.removed) == (0, 1, 0)
    stored = transactions(c)
    assert len(stored) == 2
    assert stored["b"].amount_cents == -2500


def test_absent_transaction_is_kept(fake: FakeFlinks) -> None:
    """C25."""
    account = flinks_account()
    c = connect(fake, account)
    fake.transactions = [
        flinks_tx(account, debit=10.0, transaction_id="old"),
        flinks_tx(account, debit=20.0, transaction_id="new"),
    ]
    sync(fake, c)
    fake.transactions = [flinks_tx(account, debit=20.0, transaction_id="new")]

    result = sync(fake, c)

    assert result.removed == 0
    assert set(transactions(c)) == {"old", "new"}


@pytest.mark.parametrize(
    ("last_refresh", "expected"),
    [
        (datetime.fromisoformat("2026-10-15T07:30:00+00:00"),) * 2,
        (datetime.fromisoformat("2026-10-17T00:00:00+00:00"), NOW),
        (None, NOW),
    ],
    ids=["earlier", "later", "missing"],
)
def test_last_synced_at_follows_last_refresh(
    fake: FakeFlinks, last_refresh: datetime | None, expected: datetime
) -> None:
    """C26."""
    c = connect(fake)
    fake.last_refresh = last_refresh

    sync(fake, c)

    assert connection(c).last_synced_at == expected


def test_balances_relabel_and_event(
    fake: FakeFlinks, published: list[events.Event]
) -> None:
    """C27: balances, a transfer between two Flinks accounts labelled, one event."""
    chequing = flinks_account("Chequing", current=1000.0, available=900.0)
    savings = flinks_account(
        "Savings", type="savings", current=5000.0, available=5000.0
    )
    c = connect(fake, chequing, savings)
    fake.accounts_list = [
        dataclasses.replace(chequing, current=1500.5, available=1400.5),
        savings,
    ]
    fake.transactions = [
        flinks_tx(chequing, debit=300.0, transaction_id="out"),
        flinks_tx(savings, credit=300.0, transaction_id="in"),
    ]

    result = sync(fake, c)
    again = sync(fake, c)

    stored = accounts(c)
    assert (
        stored[chequing.account_id].balance_cents,
        stored[chequing.account_id].available_cents,
    ) == (150050, 140050)
    labels = {k: t.label for k, t in transactions(c).items()}
    assert labels == {"out": "internal_transfer", "in": "internal_transfer"}
    assert result.relabeled == 2
    assert len(published) == 1
    assert published[0].payload["connection_id"] == str(c.connection_id)
    assert not again.changed


@pytest.fixture
def nightly_fakes(
    fake: FakeFlinks, monkeypatch: pytest.MonkeyPatch
) -> tuple[NightlyFake, FakeFlinks]:
    plaid = NightlyFake()
    monkeypatch.setattr(nightly, "get_plaid_client", lambda: plaid)
    monkeypatch.setattr(nightly, "get_flinks_client", lambda: fake)
    return plaid, fake


def test_nightly_syncs_flinks(nightly_fakes: tuple[NightlyFake, FakeFlinks]) -> None:
    """C28: the job syncs a due Flinks connection through the Flinks client."""
    plaid, fake = nightly_fakes
    c = connect(fake)

    counts = run(plaid, datetime.fromisoformat("2026-10-06T06:00:00+00:00"))

    assert counts["synced"] == 1
    assert [a.login_id for a in fake.accounts_calls] == [c.login_id]
    assert plaid.synced == []
    assert connection(c).nightly_synced_on == date(2026, 10, 6)


def test_nightly_flinks_retries(nightly_fakes: tuple[NightlyFake, FakeFlinks]) -> None:
    """C28: a failing Flinks sync retries after 1, 2 and 4 hours, then the night fails."""
    plaid, fake = nightly_fakes
    c = connect(fake)
    fake.fail["accounts"] = FlinksError(http_status=500, flinks_code="INTERNAL")

    for hour in (6, 7, 9, 13):
        run(plaid, datetime.fromisoformat(f"2026-10-06T{hour:02d}:00:00+00:00"))

    row = connection(c)
    assert len(fake.accounts_calls) == 4
    assert row.failed_nights == 1
    assert row.nightly_synced_on == date(2026, 10, 6)
    assert row.login_required is False


@pytest.mark.parametrize(
    ("code", "wanted"),
    [("INVALID_LOGIN", True), ("DISABLED_LOGIN", True), ("INTERNAL", False)],
)
def test_login_codes_set_login_required(
    fake: FakeFlinks, code: str, wanted: bool
) -> None:
    """C29."""
    c = connect(fake)
    fake.fail["accounts"] = login_error(code)

    with pytest.raises(FlinksError):
        sync(fake, c)

    assert connection(c).login_required is wanted
    with get_sessionmaker()() as session:
        (view,) = service.list_connections(session, business_id=c.business_id)
    assert (view.status == "login_required") is wanted


def api_connection(flinks_fake: FakeFlinks) -> tuple[Caller, str, str, str]:
    caller, business_id = _owner({**HARBOR, "name": f"Flinks {uuid.uuid4().hex[:6]}"})
    login_id = str(uuid.uuid4())
    created = client.post(
        f"/v1/businesses/{business_id}/bank/connections",
        json={"provider": "flinks", "login_id": login_id},
        headers=caller.headers,
    )
    assert created.status_code == 201
    return caller, business_id, created.json()["id"], login_id


def test_disconnect_flinks(flinks: FakeFlinks) -> None:
    """C30: DeleteCard gets the loginId, and the bank is gone."""
    caller, business_id, connection_id, login_id = api_connection(flinks)

    response = client.delete(
        f"/v1/businesses/{business_id}/bank/connections/{connection_id}",
        headers=caller.headers,
    )

    assert response.status_code == 204
    assert flinks.deleted == [login_id]
    listed = client.get(
        f"/v1/businesses/{business_id}/bank/connections", headers=caller.headers
    )
    assert listed.json()["items"] == []


def test_disconnect_flinks_when_delete_card_fails(
    flinks: FakeFlinks,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """C30: a DeleteCard failure still deletes locally, and logs the orphan by ID."""
    configure_logging()
    caller, business_id, connection_id, login_id = api_connection(flinks)
    flinks.fail["delete"] = FlinksError(http_status=400, flinks_code="CARD_IN_USE")
    capsys.readouterr()

    response = client.delete(
        f"/v1/businesses/{business_id}/bank/connections/{connection_id}",
        headers=caller.headers,
    )

    assert response.status_code == 204
    with get_sessionmaker()() as session:
        assert session.get(BankConnection, uuid.UUID(connection_id)) is None
    logs = capsys.readouterr().out
    orphan = [line for line in logs.splitlines() if "bank_connection.orphaned" in line]
    assert len(orphan) == 1
    assert connection_id in orphan[0]
    assert login_id not in logs


def test_flinks_link_token_is_409(flinks: FakeFlinks) -> None:
    """C31."""
    caller, business_id, connection_id, _ = api_connection(flinks)

    response = client.post(
        f"/v1/businesses/{business_id}/bank/connections/{connection_id}/link-token",
        headers=caller.headers,
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Reconnect this bank: disconnect it, then connect it again."
    )
