"""Spec 17b: syncing, the nightly job and disconnecting a Yodlee connection.

Runs against a database of its own, because the nightly job syncs every connection in it.
The fake Yodlee client stands in for Yodlee; one test drives the real client over a fake
HTTP transport.
"""

import dataclasses
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import pytest
import structlog
import structlog.testing
from sqlalchemy import select, text

from app import events
from app.db import get_sessionmaker
from app.jobs import nightly
from app.jobs.run_due import run_due
from app.modules.bank_sync import repository, service
from app.modules.bank_sync.models import BankAccount, BankConnection, BankTransaction
from app.modules.bank_sync.tokens import encrypt_access_token
from app.modules.bank_sync.yodlee import HttpxYodleeClient, YodleeError
from app.settings import Settings
from tests.test_nightly_sync import JOB, TORONTO, new_business
from tests.yodlee_support import (
    FakeYodlee,
    yodlee_account,
    yodlee_transaction,
)

pytestmark = pytest.mark.usefixtures("isolated_database")

LOGIN = "hr-testlogin"
CREATED_AT = datetime(2026, 10, 5, 12, tzinfo=UTC)
NOW = datetime(2026, 10, 10, 15, tzinfo=UTC)
DAY = date(2026, 10, 1)
NO_PLAID: Any = object()


@dataclasses.dataclass(frozen=True)
class Conn:
    business_id: uuid.UUID
    connection_id: uuid.UUID
    provider_account_id: str
    account_id: str


@pytest.fixture(autouse=True)
def _empty_bank_tables() -> None:
    with get_sessionmaker()() as session:
        session.execute(
            text("TRUNCATE bank_transactions, bank_accounts, bank_connections")
        )
        session.commit()


@pytest.fixture
def fake() -> FakeYodlee:
    yodlee = FakeYodlee()
    yodlee.last_refreshed = NOW
    return yodlee


def new_connection(fake: FakeYodlee, *, last_synced_at: datetime | None = None) -> Conn:
    account = yodlee_account("Operating", current=100.0)
    fake.accounts_list = lambda: [account]
    business_id = new_business(TORONTO)
    provider_account_id = f"pa-{uuid.uuid4().hex[:10]}"
    with get_sessionmaker()() as session:
        connection = repository.insert_connection(
            session,
            business_id=business_id,
            provider="yodlee",
            provider_item_id=provider_account_id,
            provider_institution_id="16441",
            institution_name="Royal Bank of Canada",
            access_token_ciphertext=encrypt_access_token(LOGIN),
        )
        repository.insert_accounts(
            session,
            [
                service._account(
                    account, business_id=business_id, connection_id=connection.id
                )
            ],
        )
        connection.created_at = CREATED_AT
        connection.last_synced_at = last_synced_at
        session.commit()
        return Conn(business_id, connection.id, provider_account_id, account.account_id)


def sync(c: Conn, yodlee: Any, now: datetime = NOW) -> service.SyncResult:
    with get_sessionmaker()() as session:
        return service.sync_connection(
            session,
            NO_PLAID,
            business_id=c.business_id,
            connection_id=c.connection_id,
            now=now,
            yodlee=yodlee,
        )


def connection_row(c: Conn) -> BankConnection:
    with get_sessionmaker()() as session:
        row = session.scalars(
            select(BankConnection).where(BankConnection.id == c.connection_id)
        ).one()
        session.expunge_all()
        return row


def transactions(c: Conn) -> list[BankTransaction]:
    with get_sessionmaker()() as session:
        rows = list(
            session.scalars(
                select(BankTransaction).where(
                    BankTransaction.business_id == c.business_id
                )
            )
        )
        session.expunge_all()
        return rows


def balance(c: Conn) -> int | None:
    with get_sessionmaker()() as session:
        return session.scalars(
            select(BankAccount.balance_cents).where(
                BankAccount.business_id == c.business_id
            )
        ).one()


@pytest.fixture
def seen() -> Iterator[list[events.Event]]:
    received: list[events.Event] = []
    events.subscribe("transactions.synced", received.append)
    yield received
    events.unsubscribe("transactions.synced", received.append)


def test_stored_amount_sign(fake: FakeYodlee) -> None:
    c = new_connection(fake)
    # The client reports a magnitude with Plaid's sign: positive is money out.
    fake.transaction_list = [
        yodlee_transaction("1", c.account_id, amount=25.0, day=DAY),
        yodlee_transaction("2", c.account_id, amount=-25.0, day=DAY),
    ]

    sync(c, fake)

    assert {t.description: t.amount_cents for t in transactions(c)} == {
        "Payment 1": -2500,
        "Payment 2": 2500,
    }


def yodlee_transport(transaction_id: int) -> httpx.MockTransport:
    """Yodlee's answers for provider account 4242 and its one account, 777."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/auth/token"):
            return httpx.Response(
                201,
                json={"token": {"accessToken": "t", "issuedAt": "x", "expiresIn": 1}},
            )
        if path.endswith("/providerAccounts/4242"):
            return httpx.Response(
                200,
                json={
                    "providerAccount": [
                        {
                            "providerId": 16441,
                            "dataset": [{"lastUpdated": "2026-10-10T10:00:00Z"}],
                        }
                    ]
                },
            )
        if path.endswith("/accounts"):
            return httpx.Response(
                200,
                json={
                    "account": [
                        {
                            "id": 777,
                            "CONTAINER": "bank",
                            "accountType": "CHECKING",
                            "accountName": "Operating",
                            "providerAccountId": 4242,
                            "balance": {"amount": 100.0, "currency": "CAD"},
                        }
                    ]
                },
            )
        if path.endswith("/transactions"):
            first = request.url.params["skip"] == "0"
            return httpx.Response(
                200,
                json={
                    "transaction": [
                        {
                            "id": transaction_id,
                            "accountId": 777,
                            "baseType": "DEBIT",
                            "status": "POSTED",
                            "date": "2026-10-01",
                            "amount": {"amount": 12.34, "currency": "CAD"},
                            "description": {"simple": "Coffee"},
                        }
                    ]
                }
                if first
                else {},
            )
        raise AssertionError(path)

    return httpx.MockTransport(handler)


def test_transaction_id_prefixed(fake: FakeYodlee) -> None:
    c = new_connection(fake)
    with get_sessionmaker()() as session:
        connection = session.get(BankConnection, c.connection_id)
        account = session.scalars(
            select(BankAccount).where(BankAccount.business_id == c.business_id)
        ).one()
        assert connection is not None
        connection.provider_item_id = "4242"
        account.provider_account_id = "777"
        session.commit()
    client = HttpxYodleeClient(
        Settings.model_construct(yodlee_api_url="https://yodlee.test/ysl"),
        transport=yodlee_transport(123),
    )

    sync(c, client)

    assert [t.provider_transaction_id for t in transactions(c)] == ["yodlee:123"]


def test_sync_upserts_and_publishes(fake: FakeYodlee, seen: list[events.Event]) -> None:
    c = new_connection(fake)
    fake.transaction_list = [
        yodlee_transaction(str(i), c.account_id, amount=10.0 + i, day=DAY)
        for i in range(3)
    ]

    result = sync(c, fake)

    assert result.added == 3
    assert len(transactions(c)) == 3
    assert [e.payload["added"] for e in seen] == [3]


def test_sync_twice_changes_nothing(fake: FakeYodlee, seen: list[events.Event]) -> None:
    c = new_connection(fake)
    fake.transaction_list = [
        yodlee_transaction("1", c.account_id, amount=10.0, day=DAY)
    ]
    sync(c, fake)
    published = len(seen)

    second = sync(c, fake, NOW + timedelta(hours=1))

    assert (second.added, second.modified, second.removed) == (0, 0, 0)
    assert len(transactions(c)) == 1
    assert len(seen) == published


def test_sync_window_first_and_later(fake: FakeYodlee) -> None:
    c = new_connection(fake)

    sync(c, fake)
    sync(c, fake, NOW + timedelta(hours=1))

    assert fake.transaction_from_dates == [
        NOW.date() - timedelta(days=730),
        (NOW + timedelta(hours=1)).date() - timedelta(days=90),
    ]


def test_last_synced_at_is_earlier_of(fake: FakeYodlee) -> None:
    c = new_connection(fake)
    fake.last_refreshed = NOW - timedelta(hours=10)

    sync(c, fake)
    assert connection_row(c).last_synced_at == NOW - timedelta(hours=10)

    fake.last_refreshed = NOW + timedelta(hours=1)
    sync(c, fake, NOW + timedelta(minutes=1))
    assert connection_row(c).last_synced_at == NOW + timedelta(minutes=1)


def test_login_required_status(fake: FakeYodlee) -> None:
    c = new_connection(fake)
    fake.needs_login = True

    with pytest.raises(YodleeError):
        sync(c, fake)

    assert connection_row(c).login_required is True
    with get_sessionmaker()() as session:
        (view,) = service.list_connections(session, business_id=c.business_id)
    assert view.status == "login_required"


def test_sync_failure_rolls_back(fake: FakeYodlee) -> None:
    c = new_connection(fake)
    fake.accounts_list = lambda: [
        dataclasses.replace(
            yodlee_account("Operating", current=5000.0), account_id=c.account_id
        )
    ]
    fake.transaction_list = [
        yodlee_transaction("1", c.account_id, amount=10.0, day=DAY)
    ]
    fake.fail["transactions"] = YodleeError(http_status=500, error_code="Y902")

    with pytest.raises(YodleeError):
        sync(c, fake)

    assert transactions(c) == []
    assert balance(c) == 10000
    assert connection_row(c).last_synced_at is None


# The nightly job


@pytest.fixture
def nightly_clients(fake: FakeYodlee, monkeypatch: pytest.MonkeyPatch) -> FakeYodlee:
    monkeypatch.setattr(nightly, "get_plaid_client", lambda: NO_PLAID)
    monkeypatch.setattr(nightly, "get_yodlee_client", lambda: fake)
    return fake


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[misc]


def test_nightly_syncs_due_yodlee(nightly_clients: FakeYodlee) -> None:
    c = new_connection(nightly_clients)
    nightly_clients.last_refreshed = utc(2026, 10, 6, 5)
    nightly_clients.transaction_list = [
        yodlee_transaction("1", c.account_id, amount=10.0, day=DAY)
    ]

    summary = run_due(utc(2026, 10, 6, 6))

    assert dict(summary[JOB])["synced"] == 1
    assert len(transactions(c)) == 1
    assert connection_row(c).last_synced_at == utc(2026, 10, 6, 5)


def test_nightly_syncs_due_yodlee_retries_then_ends_night(
    nightly_clients: FakeYodlee,
) -> None:
    c = new_connection(nightly_clients)
    nightly_clients.fail["transactions"] = YodleeError(
        http_status=500, error_code="Y902"
    )

    run_due(utc(2026, 10, 6, 6))
    first = connection_row(c)
    assert first.nightly_attempts == 1
    assert first.next_nightly_attempt_at == utc(2026, 10, 6, 7)

    # Retries after 1, 2 and 4 hours; the fourth failure ends the night.
    for hour in (7, 9, 13):
        run_due(utc(2026, 10, 6, hour))

    last = connection_row(c)
    assert last.failed_nights == 1
    assert last.nightly_synced_on == date(2026, 10, 6)
    assert last.next_nightly_attempt_at is None


# Disconnect


def test_disconnect_deletes_remote_first(fake: FakeYodlee) -> None:
    c = new_connection(fake)
    still_stored_at_delete: list[bool] = []
    original = fake.delete_provider_account

    def delete(login_name: str, provider_account_id: str) -> None:
        with get_sessionmaker()() as session:
            still_stored_at_delete.append(
                session.get(BankConnection, c.connection_id) is not None
            )
        original(login_name, provider_account_id)

    fake.delete_provider_account = delete  # type: ignore[method-assign]

    with get_sessionmaker()() as session:
        service.disconnect_bank(
            session,
            NO_PLAID,
            business_id=c.business_id,
            connection_id=c.connection_id,
            user_id=uuid.uuid4(),
            yodlee=fake,
        )

    assert still_stored_at_delete == [True]
    assert fake.deleted == [(LOGIN, c.provider_account_id)]
    with get_sessionmaker()() as session:
        assert session.get(BankConnection, c.connection_id) is None


def test_disconnect_remote_failure(fake: FakeYodlee) -> None:
    c = new_connection(fake)
    fake.transaction_list = [
        yodlee_transaction("1", c.account_id, amount=10.0, day=DAY)
    ]
    sync(c, fake)
    fake.fail["delete"] = YodleeError(http_status=500, error_code="Y902")

    with get_sessionmaker()() as session, pytest.raises(YodleeError):
        service.disconnect_bank(
            session,
            NO_PLAID,
            business_id=c.business_id,
            connection_id=c.connection_id,
            user_id=uuid.uuid4(),
            yodlee=fake,
        )

    assert connection_row(c).id == c.connection_id
    assert balance(c) == 10000
    assert len(transactions(c)) == 1


def test_disconnect_remote_not_found(fake: FakeYodlee) -> None:
    c = new_connection(fake)
    sent: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append((request.method, request.url.path))
        if request.url.path.endswith("/auth/token"):
            return httpx.Response(
                201,
                json={"token": {"accessToken": "t", "issuedAt": "x", "expiresIn": 1}},
            )
        return httpx.Response(400, json={"errorCode": "Y807"})

    client = HttpxYodleeClient(
        Settings.model_construct(yodlee_api_url="https://yodlee.test/ysl"),
        transport=httpx.MockTransport(handler),
    )

    with get_sessionmaker()() as session:
        service.disconnect_bank(
            session,
            NO_PLAID,
            business_id=c.business_id,
            connection_id=c.connection_id,
            user_id=uuid.uuid4(),
            yodlee=client,
        )

    assert not any(method == "DELETE" for method, _ in sent)
    with get_sessionmaker()() as session:
        assert session.get(BankConnection, c.connection_id) is None


def test_disconnect_when_yodlee_is_off_deletes_locally(fake: FakeYodlee) -> None:
    c = new_connection(fake)
    fake.transaction_list = [
        yodlee_transaction("1", c.account_id, amount=10.0, day=DAY)
    ]
    sync(c, fake)

    with structlog.testing.capture_logs() as logs, get_sessionmaker()() as session:
        service.disconnect_bank(
            session,
            NO_PLAID,
            business_id=c.business_id,
            connection_id=c.connection_id,
            user_id=uuid.uuid4(),
            yodlee=None,
        )

    assert transactions(c) == []
    with get_sessionmaker()() as session:
        assert session.get(BankConnection, c.connection_id) is None
    orphaned = [e for e in logs if e["event"] == "bank_connection.orphaned"]
    assert [e["provider_item_id"] for e in orphaned] == [c.provider_account_id]
